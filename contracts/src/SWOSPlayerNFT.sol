// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721Enumerable.sol";
import "@openzeppelin/contracts/access/Ownable2Step.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/Strings.sol";

/**
 * @title SWOSPlayerNFT
 * @notice ERC-721 representing players in the SWOS420 universe.
 *
 * Each token stores:
 *   - Immutable base skills (7 × uint8, set at mint, never change)
 *   - Dynamic form (-100..+100), value, goals (updated by oracle)
 *
 * Effective skill = base × (100 + form) / 100, clamped 0-15.
 * Value formula mirrors Python `calculate_current_value()`.
 *
 * @dev Deployment target: Base L2 (Sepolia first, then mainnet).
 */
contract SWOSPlayerNFT is ERC721, ERC721Enumerable, Ownable2Step, ReentrancyGuard, Pausable {

    // ── Data Structures ─────────────────────────────────────────────────

    struct Player {
        string name;
        uint8[7] baseSkills;    // [PA, VE, HE, TA, CO, SP, FI] — immutable
        int8 form;              // -100 to +100
        uint256 value;          // wei-denominated market value
        uint8 age;
        uint16 seasonGoals;
        uint16 totalGoals;
    }

    // ── State ────────────────────────────────────────────────────────────

    using Strings for uint256;

    mapping(uint256 => Player) private _players;
    address public oracle;
    string private _baseTokenURI;
    mapping(uint256 => string) private _tokenURIs;

    // ── Events ───────────────────────────────────────────────────────────

    event PlayerMinted(uint256 indexed tokenId, string name, uint8[7] baseSkills);
    event FormUpdated(uint256 indexed tokenId, int8 newForm, uint256 newValue);
    event OracleUpdated(address indexed oldOracle, address indexed newOracle);
    event SeasonReset(uint256 indexed tokenId);
    event TokenURIUpdated(uint256 indexed tokenId, string uri);
    event BaseURIUpdated(string newBaseURI);

    // ── Errors ───────────────────────────────────────────────────────────

    error OnlyOracle();
    error PlayerDoesNotExist(uint256 tokenId);

    // ── Modifiers ────────────────────────────────────────────────────────

    modifier onlyOracle() {
        if (msg.sender != oracle) revert OnlyOracle();
        _;
    }

    modifier playerExists(uint256 tokenId) {
        if (_ownerOf(tokenId) == address(0)) revert PlayerDoesNotExist(tokenId);
        _;
    }

    // ── Constructor ──────────────────────────────────────────────────────

    constructor() ERC721("SWOS Player", "SWP") Ownable(msg.sender) {}

    // ── Admin ────────────────────────────────────────────────────────────

    function setOracle(address newOracle) external onlyOwner {
        emit OracleUpdated(oracle, newOracle);
        oracle = newOracle;
    }

    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    // ── Metadata URIs ───────────────────────────────────────────────────

    /// @notice Set the base URI used as fallback for tokens without individual URIs.
    function setBaseURI(string calldata baseURI_) external onlyOwner {
        _baseTokenURI = baseURI_;
        emit BaseURIUpdated(baseURI_);
    }

    /// @notice Set the metadata URI for a single token (e.g. ar://<txId>).
    function setTokenURI(uint256 tokenId, string calldata uri) external onlyOwner playerExists(tokenId) {
        _tokenURIs[tokenId] = uri;
        emit TokenURIUpdated(tokenId, uri);
    }

    /// @notice Batch-set metadata URIs for multiple tokens.
    function setTokenURIBatch(
        uint256[] calldata tokenIds,
        string[] calldata uris
    ) external onlyOwner {
        require(tokenIds.length == uris.length, "Array length mismatch");
        for (uint256 i = 0; i < tokenIds.length; i++) {
            if (_ownerOf(tokenIds[i]) == address(0)) revert PlayerDoesNotExist(tokenIds[i]);
            _tokenURIs[tokenIds[i]] = uris[i];
            emit TokenURIUpdated(tokenIds[i], uris[i]);
        }
    }

    // ── Minting ──────────────────────────────────────────────────────────

    /// @notice Mint a single player NFT with immutable base skills.
    function mintPlayer(
        address to,
        uint256 tokenId,
        string calldata name,
        uint8[7] calldata baseSkills,
        uint8 age,
        uint256 initialValue
    ) external onlyOwner whenNotPaused {
        _safeMint(to, tokenId);
        _players[tokenId] = Player({
            name: name,
            baseSkills: baseSkills,
            form: 0,
            value: initialValue,
            age: age,
            seasonGoals: 0,
            totalGoals: 0
        });
        emit PlayerMinted(tokenId, name, baseSkills);
    }

    /// @notice Batch mint for initial roster deployment.
    function mintBatch(
        address to,
        uint256[] calldata tokenIds,
        string[] calldata names,
        uint8[7][] calldata skills,
        uint8[] calldata ages,
        uint256[] calldata values
    ) external onlyOwner whenNotPaused {
        uint256 len = tokenIds.length;
        require(
            len == names.length && len == skills.length &&
            len == ages.length && len == values.length,
            "Array length mismatch"
        );
        for (uint256 i = 0; i < len; i++) {
            _safeMint(to, tokenIds[i]);
            _players[tokenIds[i]] = Player({
                name: names[i],
                baseSkills: skills[i],
                form: 0,
                value: values[i],
                age: ages[i],
                seasonGoals: 0,
                totalGoals: 0
            });
            emit PlayerMinted(tokenIds[i], names[i], skills[i]);
        }
    }

    // ── Oracle Updates ───────────────────────────────────────────────────

    /// @notice Update after matchday: form + goals → recalculate value.
    function updateForm(
        uint256 tokenId,
        int8 newForm,
        uint16 newGoals
    ) external onlyOracle nonReentrant playerExists(tokenId) whenNotPaused {
        Player storage p = _players[tokenId];
        p.form = newForm;
        p.seasonGoals += newGoals;
        p.totalGoals += newGoals;

        // ── SWOS value formula (mirrors Python calculate_current_value) ──
        // form_mod = 1.0 + form / 100
        // goal_bonus = 1.0 + season_goals * 0.02
        // age_factor = 1.0 if age < 30, else max(0.1, 1 - (age-29)*0.1)
        uint256 formMod = uint256(int256(100) + int256(newForm));     // 0..200
        uint256 goalBonus = 100 + uint256(p.seasonGoals) * 2;        // 100..
        uint256 ageFactor;
        if (p.age < 30) {
            ageFactor = 100;
        } else {
            uint256 decay = (uint256(p.age) - 29) * 10;
            ageFactor = decay >= 90 ? 10 : 100 - decay;
        }

        // value = base × form_mod × goal_bonus × age_factor / 1_000_000
        p.value = (p.value * formMod * goalBonus * ageFactor) / 1_000_000;
        if (p.value < 25_000) p.value = 25_000; // floor

        emit FormUpdated(tokenId, newForm, p.value);
    }

    /// @notice Batch oracle update for all players after matchday.
    function batchUpdateForm(
        uint256[] calldata tokenIds,
        int8[] calldata forms,
        uint16[] calldata goals
    ) external onlyOracle nonReentrant whenNotPaused {
        require(tokenIds.length == forms.length && forms.length == goals.length, "Length mismatch");
        for (uint256 i = 0; i < tokenIds.length; i++) {
            if (_ownerOf(tokenIds[i]) == address(0)) continue;
            Player storage p = _players[tokenIds[i]];
            p.form = forms[i];
            p.seasonGoals += goals[i];
            p.totalGoals += goals[i];

            uint256 formMod = uint256(int256(100) + int256(forms[i]));
            uint256 goalBonus = 100 + uint256(p.seasonGoals) * 2;
            uint256 ageFactor;
            if (p.age < 30) { ageFactor = 100; }
            else {
                uint256 decay = (uint256(p.age) - 29) * 10;
                ageFactor = decay >= 90 ? 10 : 100 - decay;
            }
            p.value = (p.value * formMod * goalBonus * ageFactor) / 1_000_000;
            if (p.value < 25_000) p.value = 25_000;

            emit FormUpdated(tokenIds[i], forms[i], p.value);
        }
    }

    /// @notice Reset season goals (called at season end).
    function resetSeason(uint256 tokenId) external onlyOracle playerExists(tokenId) {
        _players[tokenId].seasonGoals = 0;
        _players[tokenId].age += 1;
        emit SeasonReset(tokenId);
    }

    // ── Views ────────────────────────────────────────────────────────────

    /// @notice Get full player data.
    function getPlayer(uint256 tokenId) external view playerExists(tokenId) returns (Player memory) {
        return _players[tokenId];
    }

    /// @notice Compute effective skills: base × (100 + form) / 100, clamped 0-15.
    function getEffectiveSkills(uint256 tokenId) external view playerExists(tokenId) returns (uint8[7] memory) {
        Player memory p = _players[tokenId];
        uint8[7] memory eff;
        for (uint256 i = 0; i < 7; i++) {
            int256 calc = int256(uint256(p.baseSkills[i])) * (int256(100) + int256(p.form)) / 100;
            if (calc > 15) calc = 15;
            if (calc < 0) calc = 0;
            eff[i] = uint8(uint256(calc));
        }
        return eff;
    }

    /// @notice Returns the metadata URI for a token.
    /// @dev Per-token URI takes priority over baseURI + tokenId + ".json".
    function tokenURI(uint256 tokenId) public view override playerExists(tokenId) returns (string memory) {
        // Per-token URI (set via setTokenURI / setTokenURIBatch)
        string memory _uri = _tokenURIs[tokenId];
        if (bytes(_uri).length > 0) return _uri;

        // Fallback: baseURI + tokenId + ".json"
        string memory base = _baseTokenURI;
        if (bytes(base).length > 0) {
            return string.concat(base, tokenId.toString(), ".json");
        }

        return "";
    }

    // ── ERC721 Overrides (Enumerable compatibility) ──────────────────────

    function _update(address to, uint256 tokenId, address auth)
        internal override(ERC721, ERC721Enumerable) returns (address)
    {
        return super._update(to, tokenId, auth);
    }

    function _increaseBalance(address account, uint128 value)
        internal override(ERC721, ERC721Enumerable)
    {
        super._increaseBalance(account, value);
    }

    function supportsInterface(bytes4 interfaceId)
        public view override(ERC721, ERC721Enumerable) returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
}
