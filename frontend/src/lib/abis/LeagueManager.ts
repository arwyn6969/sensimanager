export const LeagueManagerABI = [
  {
    type: "function",
    name: "getTeam",
    inputs: [
      { name: "season", type: "uint256" },
      { name: "teamCode", type: "bytes32" },
    ],
    outputs: [
      {
        name: "",
        type: "tuple",
        components: [
          { name: "manager", type: "address" },
          { name: "playerTokenIds", type: "uint256[]" },
          { name: "points", type: "uint256" },
          { name: "goalsFor", type: "uint256" },
          { name: "goalsAgainst", type: "uint256" },
          { name: "registered", type: "bool" },
        ],
      },
    ],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "getStandings",
    inputs: [{ name: "season", type: "uint256" }],
    outputs: [{ name: "", type: "bytes32[]" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "currentSeason",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "seasonState",
    inputs: [],
    outputs: [{ name: "", type: "uint8" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "matchday",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "getMatchday",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
  },
  {
    type: "function",
    name: "wageRatePerMatch",
    inputs: [],
    outputs: [{ name: "", type: "uint256" }],
    stateMutability: "view",
  },
  {
    type: "event",
    name: "TeamRegistered",
    inputs: [
      { name: "season", type: "uint256", indexed: true },
      { name: "teamCode", type: "bytes32", indexed: true },
      { name: "manager", type: "address", indexed: false },
    ],
  },
  {
    type: "event",
    name: "SeasonStarted",
    inputs: [
      { name: "season", type: "uint256", indexed: true },
      { name: "teamCount", type: "uint256", indexed: false },
    ],
  },
  {
    type: "event",
    name: "MatchdaySettled",
    inputs: [
      { name: "season", type: "uint256", indexed: true },
      { name: "matchday", type: "uint256", indexed: false },
    ],
  },
  {
    type: "event",
    name: "WagesDistributed",
    inputs: [
      { name: "season", type: "uint256", indexed: true },
      { name: "matchday", type: "uint256", indexed: false },
      { name: "totalWages", type: "uint256", indexed: false },
    ],
  },
] as const;
