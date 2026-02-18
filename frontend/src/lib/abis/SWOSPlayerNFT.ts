export const SWOSPlayerNFTABI = [
  {
    type: "function",
    name: "getPlayer",
    inputs: [{ name: "tokenId", type: "uint256" }],
    outputs: [
      {
        name: "",
        type: "tuple",
        components: [
          { name: "name", type: "string" },
          { name: "baseSkills", type: "uint8[7]" },
          { name: "form", type: "int8" },
          { name: "value", type: "uint256" },
          { name: "age", type: "uint8" },
          { name: "seasonGoals", type: "uint16" },
          { name: "totalGoals", type: "uint16" },
        ],
      },
    ],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "getEffectiveSkills",
    inputs: [{ name: "tokenId", type: "uint256" }],
    outputs: [{ name: "", type: "uint8[7]" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "totalSupply",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "tokenByIndex",
    inputs: [{ name: "index", type: "uint256" }],
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "ownerOf",
    inputs: [{ name: "tokenId", type: "uint256" }],
    outputs: [{ name: "", type: "address" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "balanceOf",
    inputs: [{ name: "owner", type: "address" }],
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "oracle",
    inputs: [],
    outputs: [{ name: "", type: "address" }],
    stateMutability: "view",
  },
  {
    type: "event",
    name: "PlayerMinted",
    inputs: [
      { name: "tokenId", type: "uint256", indexed: true },
      { name: "name", type: "string", indexed: false },
      { name: "baseSkills", type: "uint8[7]", indexed: false },
    ],
  },
  {
    type: "event",
    name: "FormUpdated",
    inputs: [
      { name: "tokenId", type: "uint256", indexed: true },
      { name: "newForm", type: "int8", indexed: false },
      { name: "newValue", type: "uint256", indexed: false },
    ],
  },
] as const;
