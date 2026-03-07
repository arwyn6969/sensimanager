/**
 * SWOS420 HTML5 Canvas Visualizer Engine
 *
 * A broadcast-oriented 2D match visualizer that consumes live stream state
 * from overlay.html and reacts to scorelines, match phases, and structured
 * commentary events.
 */

const FORMATION_ANCHORS = {
  "4-4-2": [
    { x: 0.09, y: 0.5, role: "gk" },
    { x: 0.22, y: 0.18, role: "lb" },
    { x: 0.18, y: 0.38, role: "cb" },
    { x: 0.18, y: 0.62, role: "cb" },
    { x: 0.22, y: 0.82, role: "rb" },
    { x: 0.36, y: 0.2, role: "lm" },
    { x: 0.32, y: 0.42, role: "cm" },
    { x: 0.32, y: 0.58, role: "cm" },
    { x: 0.36, y: 0.8, role: "rm" },
    { x: 0.5, y: 0.42, role: "st" },
    { x: 0.5, y: 0.58, role: "st" },
  ],
  "4-3-3": [
    { x: 0.09, y: 0.5, role: "gk" },
    { x: 0.22, y: 0.2, role: "lb" },
    { x: 0.18, y: 0.4, role: "cb" },
    { x: 0.18, y: 0.6, role: "cb" },
    { x: 0.22, y: 0.8, role: "rb" },
    { x: 0.34, y: 0.28, role: "cm" },
    { x: 0.3, y: 0.5, role: "dm" },
    { x: 0.34, y: 0.72, role: "cm" },
    { x: 0.48, y: 0.16, role: "lw" },
    { x: 0.54, y: 0.5, role: "st" },
    { x: 0.48, y: 0.84, role: "rw" },
  ],
  "4-2-3-1": [
    { x: 0.09, y: 0.5, role: "gk" },
    { x: 0.22, y: 0.18, role: "lb" },
    { x: 0.18, y: 0.38, role: "cb" },
    { x: 0.18, y: 0.62, role: "cb" },
    { x: 0.22, y: 0.82, role: "rb" },
    { x: 0.3, y: 0.4, role: "dm" },
    { x: 0.3, y: 0.6, role: "dm" },
    { x: 0.42, y: 0.18, role: "lw" },
    { x: 0.44, y: 0.5, role: "cam" },
    { x: 0.42, y: 0.82, role: "rw" },
    { x: 0.56, y: 0.5, role: "st" },
  ],
  "5-4-1": [
    { x: 0.09, y: 0.5, role: "gk" },
    { x: 0.28, y: 0.14, role: "lwb" },
    { x: 0.18, y: 0.3, role: "cb" },
    { x: 0.16, y: 0.5, role: "cb" },
    { x: 0.18, y: 0.7, role: "cb" },
    { x: 0.28, y: 0.86, role: "rwb" },
    { x: 0.38, y: 0.24, role: "lm" },
    { x: 0.34, y: 0.42, role: "cm" },
    { x: 0.34, y: 0.58, role: "cm" },
    { x: 0.38, y: 0.76, role: "rm" },
    { x: 0.52, y: 0.5, role: "st" },
  ],
  "3-4-3": [
    { x: 0.09, y: 0.5, role: "gk" },
    { x: 0.18, y: 0.28, role: "cb" },
    { x: 0.16, y: 0.5, role: "cb" },
    { x: 0.18, y: 0.72, role: "cb" },
    { x: 0.32, y: 0.14, role: "lwb" },
    { x: 0.32, y: 0.4, role: "cm" },
    { x: 0.32, y: 0.6, role: "cm" },
    { x: 0.32, y: 0.86, role: "rwb" },
    { x: 0.48, y: 0.16, role: "lw" },
    { x: 0.54, y: 0.5, role: "st" },
    { x: 0.48, y: 0.84, role: "rw" },
  ],
};

const STYLE_PROFILES = {
  "balanced shape": {
    width: 1,
    depth: 1,
    support: 1,
    press: 1,
    verticality: 1,
    shortPassBias: 1,
    wideBias: 0.45,
    crossBias: 0.4,
    breakaway: 1,
    boxDelay: 1,
  },
  "compact defending": {
    width: 0.74,
    depth: 0.8,
    support: 0.76,
    press: 0.88,
    verticality: 0.82,
    shortPassBias: 1.04,
    wideBias: 0.18,
    crossBias: 0.24,
    breakaway: 0.88,
    boxDelay: 1.18,
  },
  "patient possession": {
    width: 1.24,
    depth: 0.98,
    support: 1.14,
    press: 1,
    verticality: 0.78,
    shortPassBias: 1.34,
    wideBias: 0.66,
    crossBias: 0.28,
    breakaway: 0.92,
    boxDelay: 1.24,
  },
  "direct transition": {
    width: 0.98,
    depth: 1.14,
    support: 1.18,
    press: 1.08,
    verticality: 1.34,
    shortPassBias: 0.78,
    wideBias: 0.36,
    crossBias: 0.38,
    breakaway: 1.36,
    boxDelay: 0.78,
  },
  "wing-heavy attacks": {
    width: 1.36,
    depth: 1.1,
    support: 1.12,
    press: 1,
    verticality: 1.04,
    shortPassBias: 0.92,
    wideBias: 1.38,
    crossBias: 1.34,
    breakaway: 1.14,
    boxDelay: 0.9,
  },
};

const ROLE_WEIGHTS = {
  gk: -0.6,
  cb: -0.34,
  lb: -0.12,
  rb: -0.12,
  lwb: -0.04,
  rwb: -0.04,
  dm: -0.16,
  cm: 0.02,
  cam: 0.16,
  lm: 0.16,
  rm: 0.16,
  lw: 0.24,
  rw: 0.24,
  st: 0.34,
};

class SWOSEngine {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext("2d", { alpha: false });
    this.width = this.canvas.width;
    this.height = this.canvas.height;

    this.ctx.imageSmoothingEnabled = false;
    this.scale = 4;
    this.assets = {};
    this.players = [];
    this.ball = this.createBall();
    this.matchState = "waiting";
    this.loadedImages = 0;
    this.lastTimestamp = 0;
    this.lastAppliedEventKey = "";
    this.randomState = 0x42042042;
    this.possessionTeam = "home";
    this.sequence = null;
    this.visualPulse = { type: "", team: null, strength: 0, expiresAt: 0 };
    this.weatherFx = { raining: false, rain: [], wind: 0, mode: "dry" };
    this.liveState = {
      status: "waiting",
      minute: 0,
      homeGoals: 0,
      awayGoals: 0,
      homeTeam: "Home",
      awayTeam: "Away",
      homeFormation: "4-4-2",
      awayFormation: "4-4-2",
      homeStyle: "balanced shape",
      awayStyle: "balanced shape",
      matchNarrative: "",
      pressureNote: "",
      weather: "dry",
      story: "",
      sessionId: "",
      latestEvent: null,
    };

    this.loadAssets();
  }

  createBall() {
    return {
      x: this.width / 2,
      y: this.height / 2,
      vx: 0,
      vy: 0,
      z: 0,
      vz: 0,
      attachedTo: null,
    };
  }

  clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  hashString(value) {
    let hash = 2166136261;
    const text = String(value || "swos420");
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  setRandomSeed(seed) {
    this.randomState = (seed >>> 0) || 0x42042042;
  }

  rand() {
    this.randomState = (this.randomState + 0x6d2b79f5) >>> 0;
    let next = this.randomState;
    next = Math.imul(next ^ (next >>> 15), next | 1);
    next ^= next + Math.imul(next ^ (next >>> 7), next | 61);
    return ((next ^ (next >>> 14)) >>> 0) / 4294967296;
  }

  randRange(min, max) {
    return min + (max - min) * this.rand();
  }

  otherTeam(team) {
    return team === "away" ? "home" : "away";
  }

  normalizeStatus(status) {
    const normalized = String(status || "waiting").toLowerCase();
    if (normalized === "ft") return "fulltime";
    if (normalized === "ht") return "halftime";
    if (
      normalized === "live"
      || normalized === "prematch"
      || normalized === "halftime"
      || normalized === "fulltime"
      || normalized === "stale"
      || normalized === "offline"
      || normalized === "waiting"
    ) {
      return normalized;
    }
    return "waiting";
  }

  normalizeFormation(formation) {
    const candidate = String(formation || "4-4-2");
    return FORMATION_ANCHORS[candidate] ? candidate : "4-4-2";
  }

  normalizeStyle(style) {
    const normalized = String(style || "balanced shape").toLowerCase();
    if (STYLE_PROFILES[normalized]) return normalized;
    if (normalized.includes("patient")) return "patient possession";
    if (normalized.includes("direct")) return "direct transition";
    if (normalized.includes("compact")) return "compact defending";
    if (normalized.includes("wing")) return "wing-heavy attacks";
    return "balanced shape";
  }

  teamPlayers(team) {
    return this.players
      .filter((player) => player.team === team)
      .sort((left, right) => left.slot - right.slot);
  }

  getTeamIdentity(team) {
    const formationKey = team === "home" ? "homeFormation" : "awayFormation";
    const styleKey = team === "home" ? "homeStyle" : "awayStyle";
    const formation = this.normalizeFormation(this.liveState[formationKey]);
    const style = this.normalizeStyle(this.liveState[styleKey]);
    return {
      formation,
      style,
      anchors: FORMATION_ANCHORS[formation],
      profile: STYLE_PROFILES[style],
    };
  }

  applyTeamShape(team, resetPositions = false) {
    const identity = this.getTeamIdentity(team);
    const existing = this.teamPlayers(team);

    if (existing.length === 0) {
      identity.anchors.forEach((anchor, index) => {
        this.players.push(this.buildPlayer(team, anchor, index));
      });
      return;
    }

    identity.anchors.forEach((anchor, index) => {
      const player = existing[index];
      const mirroredX = team === "home" ? anchor.x : 1 - anchor.x;
      player.role = anchor.role;
      player.baseX = mirroredX;
      player.baseY = anchor.y;

      if (resetPositions) {
        player.x = mirroredX * this.width;
        player.y = anchor.y * this.height;
        player.tx = player.x;
        player.ty = player.y;
      }
    });
  }

  refreshShapeAnchors(resetPositions = false) {
    this.applyTeamShape("home", resetPositions);
    this.applyTeamShape("away", resetPositions);
  }

  isWideRole(role) {
    return ["lb", "rb", "lwb", "rwb", "lm", "rm", "lw", "rw"].includes(role);
  }

  isWingBackRole(role) {
    return role === "lwb" || role === "rwb";
  }

  isBackLineRole(role) {
    return ["cb", "lb", "rb", "lwb", "rwb"].includes(role);
  }

  isHoldingRole(role) {
    return role === "dm" || role === "cm";
  }

  isStrikerRole(role) {
    return role === "st";
  }

  isAttackingRole(role) {
    return ["cam", "lm", "rm", "lw", "rw", "st"].includes(role);
  }

  isGoalkeeperRole(role) {
    return role === "gk";
  }

  getPlayerPalette(player) {
    const isKeeper = this.isGoalkeeperRole(player.role);
    if (player.team === "home") {
      return isKeeper
        ? {
            primary: "#eff7ff",
            shorts: "#11374a",
            stripe: "#00b0ff",
            outline: "#062232",
            pointer: "#00e676",
            skin: "#f5d7b5",
            hair: "#4a311f",
            boots: "#05080d",
          }
        : {
            primary: "#17c6ff",
            shorts: "#0b2030",
            stripe: "#eaf8ff",
            outline: "#062232",
            pointer: "#6ff6ff",
            skin: "#f5d7b5",
            hair: "#4a311f",
            boots: "#05080d",
          };
    }

    return isKeeper
      ? {
          primary: "#fff2cc",
          shorts: "#6b4b00",
          stripe: "#ffd740",
          outline: "#3f2700",
          pointer: "#ffd740",
          skin: "#f5d7b5",
          hair: "#4a311f",
          boots: "#05080d",
        }
      : {
          primary: "#ffc83d",
          shorts: "#4d2b00",
          stripe: "#fff6d9",
          outline: "#3f2700",
          pointer: "#ffea8a",
          skin: "#f5d7b5",
          hair: "#4a311f",
          boots: "#05080d",
        };
  }

  spriteFacing(angle) {
    if (angle > -Math.PI / 4 && angle <= Math.PI / 4) return "right";
    if (angle > Math.PI / 4 && angle <= (3 * Math.PI) / 4) return "down";
    if (angle < -Math.PI / 4 && angle >= (-3 * Math.PI) / 4) return "up";
    return "left";
  }

  pixelSpriteTemplate(direction = "down", frame = 0) {
    const templates = {
      down: [
        [
          "..hh....",
          ".hssh...",
          ".ssss...",
          ".akkkka.",
          ".akttka.",
          ".akkkka.",
          "..pppp..",
          ".pppppp.",
          ".bb..bb.",
          ".bb..bb.",
          "b......b",
          "........",
        ],
        [
          "..hh....",
          ".hssh...",
          ".ssss...",
          ".akkkka.",
          ".akttka.",
          ".akkkka.",
          "..pppp..",
          ".pppppp.",
          "bb....bb",
          ".bb..bb.",
          "..b..b..",
          "........",
        ],
      ],
      up: [
        [
          "..hh....",
          ".hhhh...",
          ".hssh...",
          ".kkkkkk.",
          ".kttttk.",
          ".kkkkkk.",
          "..pppp..",
          ".pppppp.",
          ".bb..bb.",
          ".bb..bb.",
          "b......b",
          "........",
        ],
        [
          "..hh....",
          ".hhhh...",
          ".hssh...",
          ".kkkkkk.",
          ".kttttk.",
          ".kkkkkk.",
          "..pppp..",
          ".pppppp.",
          "bb....bb",
          ".bb..bb.",
          "..b..b..",
          "........",
        ],
      ],
      side: [
        [
          "...hh...",
          "..hss...",
          "..sss...",
          "..kkkk..",
          "..kttk..",
          "..kkkk..",
          "..pppp..",
          "..pppp..",
          "...bb...",
          "..bb....",
          "..bb....",
          "........",
        ],
        [
          "...hh...",
          "..hss...",
          "..sss...",
          "..kkkk..",
          "..kttk..",
          "..kkkk..",
          "..pppp..",
          "..pppp..",
          "..bb....",
          "...bb...",
          "..bb....",
          "........",
        ],
      ],
    };
    const frames = templates[direction] || templates.down;
    return frames[frame % frames.length];
  }

  paintPixelSprite(originX, originY, palette, direction, frame, mirrored, isKeeper) {
    const template = this.pixelSpriteTemplate(direction, frame);
    const pixel = 5;
    const width = template[0].length;
    const colorMap = {
      h: palette.hair,
      s: palette.skin,
      a: palette.skin,
      k: palette.primary,
      t: palette.stripe,
      p: palette.shorts,
      b: palette.boots,
      g: isKeeper ? palette.stripe : palette.skin,
    };

    const drawCell = (x, y, color, offsetX = 0, offsetY = 0) => {
      const drawX = mirrored ? width - 1 - x : x;
      this.ctx.fillStyle = color;
      this.ctx.fillRect(originX + drawX * pixel + offsetX, originY + y * pixel + offsetY, pixel, pixel);
    };

    this.ctx.save();
    this.ctx.globalAlpha = 0.22;
    template.forEach((row, y) => {
      [...row].forEach((cell, x) => {
        if (!colorMap[cell]) return;
        drawCell(x, y, palette.outline, 1, 1);
      });
    });
    this.ctx.restore();

    template.forEach((row, y) => {
      [...row].forEach((cell, x) => {
        const color = colorMap[cell];
        if (!color) return;
        drawCell(x, y, color);
      });
    });
  }

  loadAssets() {
    const urls = {
      pitch: "assets/pitch_tile.png",
      ball: "assets/ball.png",
    };

    for (const [key, url] of Object.entries(urls)) {
      const img = new Image();
      img.src = url;
      img.onload = () => {
        this.assets[key] = img;
        this.loadedImages++;
        if (this.loadedImages === Object.keys(urls).length) {
          this.initMatch();
          requestAnimationFrame((ts) => this.tick(ts));
        }
      };
    }
  }

  buildPlayer(team, anchor, slot) {
    const mirroredX = team === "home" ? anchor.x : 1 - anchor.x;
    const x = mirroredX * this.width;
    const y = anchor.y * this.height;
    return {
      team,
      role: anchor.role,
      slot,
      baseX: mirroredX,
      baseY: anchor.y,
      x,
      y,
      tx: x,
      ty: y,
      speed: 2.2 + this.rand() * 1.2,
      stride: this.rand() * Math.PI * 2,
      aura: team === "home" ? "rgba(0, 176, 255, 0.26)" : "rgba(255, 215, 64, 0.28)",
    };
  }

  createRainDrop() {
    return {
      x: this.rand() * this.width,
      y: this.rand() * this.height,
      speed: 18 + this.rand() * 16,
      length: 18 + this.rand() * 20,
    };
  }

  configureWeather(weather) {
    const weatherText = String(weather || "").toLowerCase();
    if (weatherText === this.weatherFx.mode) {
      return;
    }

    const raining = /(rain|wet|storm)/.test(weatherText);
    this.weatherFx.raining = raining;
    this.weatherFx.mode = weatherText;
    this.weatherFx.wind = /(wind|storm)/.test(weatherText)
      ? (this.rand() < 0.5 ? -1 : 1) * (0.08 + this.rand() * 0.08)
      : 0;

    if (raining && this.weatherFx.rain.length === 0) {
      this.weatherFx.rain = Array.from({ length: 90 }, () => this.createRainDrop());
    } else if (!raining) {
      this.weatherFx.rain = [];
    }
  }

  initMatch() {
    this.pitchPattern = this.ctx.createPattern(this.assets.pitch, "repeat");
    this.players = [];
    this.refreshShapeAnchors(true);

    this.configureWeather(this.liveState.weather);
    this.resetForKickoff("home");
    this.matchState = "prematch";
  }

  pickKickoffPlayer(team) {
    return this.players.find((player) => player.team === team && this.isStrikerRole(player.role))
      || this.players.find((player) => player.team === team && player.role === "cam")
      || this.players.find((player) => player.team === team && player.role === "cm")
      || this.players.find((player) => player.team === team)
      || null;
  }

  resetForKickoff(kickoffTeam = "home") {
    this.players.forEach((player) => {
      player.x = player.baseX * this.width;
      player.y = player.baseY * this.height;
      player.tx = player.x;
      player.ty = player.y;
    });

    this.ball = this.createBall();
    const kickoffPlayer = this.pickKickoffPlayer(kickoffTeam);
    if (kickoffPlayer) {
      this.ball.attachedTo = kickoffPlayer;
      this.ball.x = kickoffPlayer.x + (kickoffTeam === "home" ? 16 : -16);
      this.ball.y = kickoffPlayer.y;
    }

    this.possessionTeam = kickoffTeam;
  }

  pickRestartTeam() {
    if ((this.liveState.homeGoals || 0) === 0 && (this.liveState.awayGoals || 0) === 0) {
      return "home";
    }

    const latestTeam = this.liveState.latestEvent?.team;
    if (latestTeam === "home" || latestTeam === "away") {
      return this.otherTeam(latestTeam);
    }

    return this.possessionTeam || "home";
  }

  syncBroadcast(snapshot = {}) {
    const status = this.normalizeStatus(snapshot.status ?? this.liveState.status);
    const latestEvent = snapshot.latestEvent ?? this.liveState.latestEvent ?? null;
    const sessionId = snapshot.sessionId ?? this.liveState.sessionId ?? "";
    const sessionChanged = sessionId && sessionId !== this.liveState.sessionId;

    this.liveState = {
      ...this.liveState,
      ...snapshot,
      status,
      sessionId,
      latestEvent,
      homeFormation: this.normalizeFormation(snapshot.homeFormation ?? this.liveState.homeFormation),
      awayFormation: this.normalizeFormation(snapshot.awayFormation ?? this.liveState.awayFormation),
      homeStyle: this.normalizeStyle(snapshot.homeStyle ?? this.liveState.homeStyle),
      awayStyle: this.normalizeStyle(snapshot.awayStyle ?? this.liveState.awayStyle),
    };

    if (sessionChanged) {
      this.setRandomSeed(this.hashString(sessionId));
      this.players = [];
      this.ball = this.createBall();
      this.matchState = "waiting";
      this.sequence = null;
      this.lastAppliedEventKey = "";
      this.visualPulse = { type: "", team: null, strength: 0, expiresAt: 0 };
      this.weatherFx = { raining: false, rain: [], wind: 0, mode: "" };
    }

    this.configureWeather(this.liveState.weather);

    if (!this.players.length) {
      this.refreshShapeAnchors(true);
    } else {
      this.refreshShapeAnchors(status !== "live");
    }

    if (status === "live" && (this.matchState === "waiting" || this.matchState === "prematch")) {
      this.resetForKickoff(this.pickRestartTeam());
      this.matchState = "playing";
      this.sequence = null;
    } else if (status === "prematch" && this.matchState !== "goal_celebration") {
      this.matchState = "prematch";
      this.sequence = null;
    } else if (status === "halftime") {
      this.startBreak("halftime");
    } else if (status === "fulltime") {
      this.startBreak("fulltime");
    } else if (status === "stale") {
      this.startBreak("stale");
    } else if (status === "offline" || status === "waiting") {
      this.matchState = "waiting";
      this.sequence = null;
    }

    const eventKey = snapshot.eventKey || "";
    if (latestEvent && eventKey && eventKey !== this.lastAppliedEventKey) {
      this.lastAppliedEventKey = eventKey;
      this.applyEventCue(latestEvent);
    }
  }

  applyEventCue(event) {
    const type = String(event?.event_type || event?.type || "").toLowerCase();
    const team = event?.team || null;
    const now = performance.now();

    if (team === "home" || team === "away") {
      this.possessionTeam = team;
    }

    this.visualPulse = {
      type,
      team,
      strength: 1,
      expiresAt: now + (type === "goal" ? 2600 : 1800),
    };

    if (type === "goal") {
      if (this.matchState !== "goal_celebration") {
        this.triggerGoalSequence(team || this.possessionTeam || "home");
      }
      return;
    }

    if (type === "yellow_card" || type === "red_card") {
      this.startStoppage("card", this.otherTeam(team || this.possessionTeam || "home"), 1900);
      return;
    }

    if (type === "save" || type === "miss") {
      this.startStoppage("chance", team || this.possessionTeam || "home", 1400);
      return;
    }

    if (type === "injury") {
      this.startStoppage("injury", this.otherTeam(team || this.possessionTeam || "home"), 2300);
      return;
    }

    if (type === "halftime") {
      this.startBreak("halftime");
      return;
    }

    if (type === "fulltime") {
      this.startBreak("fulltime");
      return;
    }

    if (type === "prematch") {
      this.matchState = "prematch";
      return;
    }

    if (type === "shape" || type === "tactical" || type === "pressure" || type === "style") {
      this.matchState = this.liveState.status === "live" ? "playing" : this.normalizeStatus(this.liveState.status);
    }
  }

  startStoppage(kind, attackingTeam, durationMs) {
    if (this.matchState === "goal_celebration") return;

    const anchorX = this.width * (attackingTeam === "home" ? 0.68 : 0.32);
    const anchorY = this.height * (0.3 + this.rand() * 0.4);
    this.sequence = {
      kind,
      team: attackingTeam,
      anchorX,
      anchorY,
      expiresAt: performance.now() + durationMs,
    };

    this.matchState = "stoppage";
    this.possessionTeam = attackingTeam;
    this.ball.attachedTo = null;
    this.ball.x = anchorX;
    this.ball.y = anchorY;
    this.ball.vx = 0;
    this.ball.vy = 0;
    this.ball.z = 0;
    this.ball.vz = 0;
  }

  startBreak(kind) {
    this.sequence = { kind, expiresAt: Number.POSITIVE_INFINITY };
    this.matchState = kind;
    this.ball.attachedTo = null;
    this.ball.x = this.width / 2;
    this.ball.y = this.height / 2;
    this.ball.vx = 0;
    this.ball.vy = 0;
    this.ball.z = 0;
    this.ball.vz = 0;
  }

  triggerGoalSequence(scorerTeam) {
    if (!this.players.length) return;

    const striker = this.pickKickoffPlayer(scorerTeam) || this.players.find((player) => player.team === scorerTeam);
    if (!striker) return;

    striker.x = scorerTeam === "home" ? this.width * 0.72 : this.width * 0.28;
    striker.y = this.height * (0.32 + this.rand() * 0.36);
    striker.tx = striker.x;
    striker.ty = striker.y;

    this.ball.attachedTo = striker;
    this.ball.x = striker.x + (scorerTeam === "home" ? 18 : -18);
    this.ball.y = striker.y;
    this.ball.z = 0;
    this.ball.vx = 0;
    this.ball.vy = 0;
    this.ball.vz = 0;
    this.possessionTeam = scorerTeam;

    this.sequence = {
      kind: "goal",
      team: scorerTeam,
      scorer: striker,
      celebrationX: scorerTeam === "home" ? this.width * 0.84 : this.width * 0.16,
      celebrationY: this.height * (0.18 + this.rand() * 0.64),
      targetX: scorerTeam === "home" ? this.width + 24 : -24,
      targetY: this.height / 2 + (this.rand() * 180 - 90),
      shotAt: performance.now() + 320,
      shotFired: false,
      expiresAt: performance.now() + 3200,
    };

    this.matchState = "goal_celebration";
  }

  deriveContext() {
    const minute = this.liveState.minute || 0;
    const homeGoals = this.liveState.homeGoals || 0;
    const awayGoals = this.liveState.awayGoals || 0;
    const scoreDiff = homeGoals - awayGoals;
    const lateFactor = this.clamp(minute / 90, 0, 1);
    const homeIdentity = this.getTeamIdentity("home");
    const awayIdentity = this.getTeamIdentity("away");
    const homeBaseTilt = (
      (homeIdentity.profile.verticality - awayIdentity.profile.verticality) * 0.18
      + (homeIdentity.profile.press - awayIdentity.profile.press) * 0.08
      + (homeIdentity.profile.support - awayIdentity.profile.support) * 0.05
    );

    let homeTilt = homeBaseTilt;
    if (scoreDiff < 0) homeTilt += 0.28 + lateFactor * 0.24;
    if (scoreDiff > 0) homeTilt -= 0.14 * lateFactor;
    if (this.possessionTeam === "home") homeTilt += 0.08;
    if (this.possessionTeam === "away") homeTilt -= 0.08;
    if (this.liveState.latestEvent?.team === "home") homeTilt += this.visualPulse.strength * 0.2;
    if (this.liveState.latestEvent?.team === "away") homeTilt -= this.visualPulse.strength * 0.2;
    homeTilt = this.clamp(homeTilt, -0.55, 0.55);

    const homeUrgencyBase = scoreDiff < 0
      ? 1.08 + lateFactor * 0.38
      : scoreDiff > 0
        ? 0.9 - lateFactor * 0.1
        : 1;
    const awayUrgencyBase = scoreDiff > 0
      ? 1.08 + lateFactor * 0.38
      : scoreDiff < 0
        ? 0.9 - lateFactor * 0.1
        : 1;

    return {
      minute,
      scoreDiff,
      lateFactor,
      homeTilt,
      intensity: this.clamp(
        0.72
          + lateFactor * 0.3
          + ((homeIdentity.profile.press + awayIdentity.profile.press) / 2 - 1) * 0.22
          + this.visualPulse.strength * 0.2,
        0.68,
        1.5,
      ),
      homeUrgency: this.clamp(homeUrgencyBase * homeIdentity.profile.breakaway, 0.76, 1.7),
      awayUrgency: this.clamp(awayUrgencyBase * awayIdentity.profile.breakaway, 0.76, 1.7),
      focusTeam: this.ball.attachedTo?.team || this.possessionTeam || (homeTilt >= 0 ? "home" : "away"),
      homeIdentity,
      awayIdentity,
    };
  }

  tick(timestamp) {
    this.update(timestamp);
    this.draw(timestamp);
    requestAnimationFrame((ts) => this.tick(ts));
  }

  updateVisualPulse(now) {
    if (!this.visualPulse.expiresAt || now >= this.visualPulse.expiresAt) {
      this.visualPulse.strength = 0;
      return;
    }

    const remaining = this.visualPulse.expiresAt - now;
    const lifetime = this.visualPulse.type === "goal" ? 2600 : 1800;
    this.visualPulse.strength = this.clamp(remaining / lifetime, 0, 1);
  }

  updateWeather() {
    if (!this.weatherFx.raining) return;

    this.weatherFx.rain.forEach((drop) => {
      drop.x += this.weatherFx.wind * 32;
      drop.y += drop.speed;
      if (drop.y > this.height + drop.length || drop.x < -20 || drop.x > this.width + 20) {
        drop.x = this.rand() * this.width;
        drop.y = -drop.length;
      }
    });
  }

  update(timestamp) {
    this.updateVisualPulse(timestamp);
    this.updateWeather();

    if (!this.players.length) return;

    if (this.matchState === "goal_celebration") {
      this.updateGoalCelebration(timestamp);
      return;
    }

    if (this.matchState === "stoppage") {
      this.updateStoppage(timestamp);
      return;
    }

    if (
      this.matchState === "halftime"
      || this.matchState === "fulltime"
      || this.matchState === "prematch"
      || this.matchState === "waiting"
      || this.matchState === "stale"
      || this.matchState === "offline"
    ) {
      this.updateIdleState(timestamp);
      return;
    }

    this.updateOpenPlay(timestamp);
  }

  roleWeight(role) {
    return ROLE_WEIGHTS[role] ?? 0;
  }

  closestPlayer(x, y, team) {
    let winner = null;
    let best = Number.POSITIVE_INFINITY;

    for (const player of this.players) {
      if (team && player.team !== team) continue;
      const distance = Math.hypot(player.x - x, player.y - y);
      if (distance < best) {
        best = distance;
        winner = player;
      }
    }

    return winner;
  }

  movePlayer(player, speedMultiplier = 1) {
    const angle = Math.atan2(player.ty - player.y, player.tx - player.x);
    const distance = Math.hypot(player.tx - player.x, player.ty - player.y);
    const speed = player.speed * speedMultiplier;

    if (distance > speed) {
      player.x += Math.cos(angle) * speed;
      player.y += Math.sin(angle) * speed;
    } else {
      player.x = player.tx;
      player.y = player.ty;
    }

    player.x = this.clamp(player.x, 24, this.width - 24);
    player.y = this.clamp(player.y, 40, this.height - 40);
  }

  shootBall(player, targetX, targetY, power = 28) {
    this.ball.attachedTo = null;
    const angle = Math.atan2(targetY - player.y, targetX - player.x);
    this.ball.vx = Math.cos(angle) * power;
    this.ball.vy = Math.sin(angle) * power;
    this.ball.vz = 8 + this.rand() * 4;
  }

  passBall(player, teammate) {
    this.ball.attachedTo = null;
    const angle = Math.atan2(teammate.y - player.y, teammate.x - player.x);
    const distance = Math.hypot(teammate.y - player.y, teammate.x - player.x);
    const power = this.clamp(distance / 18, 12, 26);
    this.ball.vx = Math.cos(angle) * power;
    this.ball.vy = Math.sin(angle) * power;
    this.ball.vz = 3 + this.rand() * 2;
  }

  bestPassTarget(player, mode = "build") {
    const { profile } = this.getTeamIdentity(player.team);
    const direction = player.team === "home" ? 1 : -1;
    const ranked = this.players
      .filter((candidate) => candidate.team === player.team && candidate !== player)
      .map((candidate) => {
        const distance = Math.hypot(candidate.x - player.x, candidate.y - player.y);
        const progress = direction * (candidate.x - player.x);
        const widthFactor = Math.abs(candidate.y - this.height / 2) / (this.height / 2);
        const shortBonus = 1 - this.clamp(distance / 480, 0, 1);
        let score = progress / 260;
        score += shortBonus * (0.7 + profile.shortPassBias * 0.45);
        score += widthFactor * profile.wideBias * 0.45;
        score += this.isStrikerRole(candidate.role) ? 0.18 * profile.support : 0;
        score += this.isHoldingRole(candidate.role) && distance < 220 ? 0.12 * profile.shortPassBias : 0;
        score += this.isAttackingRole(candidate.role) ? 0.18 * profile.verticality : 0;

        if (mode === "cross") {
          score += this.isStrikerRole(candidate.role) ? 0.85 + profile.crossBias * 0.35 : -0.1;
          score += widthFactor * 0.12;
        }

        if (this.isWideRole(player.role) && this.isStrikerRole(candidate.role)) {
          score += 0.28 * profile.crossBias;
        }
        if (profile.verticality > 1 && progress > 120) {
          score += 0.25 * profile.verticality;
        }

        score += this.rand() * 0.1;
        return { candidate, score };
      })
      .sort((left, right) => right.score - left.score);

    if (ranked.length === 0) return null;
    const pool = ranked.slice(0, Math.min(3, ranked.length));
    return pool[Math.floor(this.rand() * pool.length)].candidate;
  }

  updateBallPhysics(focusTeam) {
    if (this.ball.attachedTo) {
      this.possessionTeam = this.ball.attachedTo.team;
      return;
    }

    this.ball.x += this.ball.vx;
    this.ball.y += this.ball.vy;
    this.ball.z += this.ball.vz;
    this.ball.vz -= 0.42;
    this.ball.vx += this.weatherFx.wind * 0.04;

    if (this.ball.z < 0) {
      this.ball.z = 0;
      this.ball.vz *= this.weatherFx.raining ? -0.4 : -0.58;
      this.ball.vx *= this.weatherFx.raining ? 0.97 : 0.95;
      this.ball.vy *= this.weatherFx.raining ? 0.97 : 0.95;
    }

    if (this.ball.z < 10 && Math.abs(this.ball.vx) < 15 && Math.abs(this.ball.vy) < 15) {
      const preferred = this.closestPlayer(this.ball.x, this.ball.y, focusTeam);
      const nearest = preferred || this.closestPlayer(this.ball.x, this.ball.y);
      if (nearest && Math.hypot(nearest.x - this.ball.x, nearest.y - this.ball.y) < 28) {
        this.ball.attachedTo = nearest;
        this.ball.vx = 0;
        this.ball.vy = 0;
        this.ball.vz = 0;
        this.possessionTeam = nearest.team;
      }
    }

    if (this.ball.x < -40 || this.ball.x > this.width + 40 || this.ball.y < -40 || this.ball.y > this.height + 40) {
      const restartPlayer = this.closestPlayer(this.width / 2, this.height / 2, focusTeam) || this.pickKickoffPlayer(focusTeam);
      this.ball.attachedTo = restartPlayer;
      this.ball.x = restartPlayer ? restartPlayer.x : this.width / 2;
      this.ball.y = restartPlayer ? restartPlayer.y : this.height / 2;
      this.ball.vx = 0;
      this.ball.vy = 0;
      this.ball.z = 0;
      this.ball.vz = 0;
      this.possessionTeam = focusTeam;
    }
  }

  updateOpenPlay(timestamp) {
    const context = this.deriveContext();
    this.updateBallPhysics(context.focusTeam);
    const holder = this.ball.attachedTo;

    for (const player of this.players) {
      const teamDirection = player.team === "home" ? 1 : -1;
      const identity = player.team === "home" ? context.homeIdentity : context.awayIdentity;
      const profile = identity.profile;
      const teamTilt = player.team === "home" ? context.homeTilt : -context.homeTilt;
      const roleWeight = this.roleWeight(player.role);
      const baseX = player.baseX * this.width;
      const baseY = player.baseY * this.height;
      const laneFromCenter = baseY - this.height / 2;
      const wideExtra = this.isWideRole(player.role) ? 0.18 : 0;
      const widthFactor = profile.width * (1 + wideExtra * profile.wideBias);
      const shapedY = this.height / 2 + laneFromCenter * widthFactor;
      const depthBoost = (profile.depth - 1) * 110 + roleWeight * 42;
      const lateralDrift = Math.sin(timestamp / (480 + player.slot * 9) + player.stride)
        * (16 + profile.width * 8 + (this.isWideRole(player.role) ? 18 : 6));
      const shapeX = baseX
        + (this.ball.x - this.width / 2) * (0.08 + profile.verticality * 0.05)
        + teamDirection * (depthBoost + teamTilt * (120 + roleWeight * 130));
      const shapeY = shapedY
        + (this.ball.y - this.height / 2) * (0.08 + profile.support * 0.07)
        - Math.sign(laneFromCenter || 1) * (1 - profile.width) * (this.isBackLineRole(player.role) ? 60 : 18);
      const urgency = player.team === "home" ? context.homeUrgency : context.awayUrgency;
      const speedMultiplier = context.intensity
        * urgency
        * (0.9 + profile.press * 0.14)
        * (this.isWingBackRole(player.role) || this.isWideRole(player.role) ? 1.03 : 1);

      if (this.ball.attachedTo === player) {
        const wideTargetY = this.isWideRole(player.role)
          ? shapedY
          : this.height / 2 + Math.sin(timestamp / 260 + player.stride) * 52;
        const targetX = player.team === "home"
          ? this.width - (this.isStrikerRole(player.role) ? 86 : 126 + (profile.boxDelay - 1) * 40)
          : 126 + (this.isStrikerRole(player.role) ? -40 : 0) + (profile.boxDelay - 1) * 40;
        const targetY = this.clamp(wideTargetY + Math.sin(timestamp / 280 + player.stride) * 34, 90, this.height - 90);
        player.tx = targetX;
        player.ty = targetY;

        const distanceToGoal = Math.hypot(player.x - targetX, player.y - this.height / 2);
        const actionRate = 0.0065
          * context.intensity
          * urgency
          * (0.9 + profile.verticality * 0.45)
          * (this.isStrikerRole(player.role) ? 1.3 : 1);

        if (this.rand() < actionRate) {
          const wideCrossZone = this.isWideRole(player.role)
            && ((player.team === "home" && player.x > this.width * 0.62)
              || (player.team === "away" && player.x < this.width * 0.38));
          const shootWindow = distanceToGoal < (profile.shortPassBias > 1 ? 330 : 400)
            || (context.lateFactor > 0.76 && urgency > 1.02);

          if (wideCrossZone && this.rand() < 0.34 * profile.crossBias) {
            const crossTarget = this.bestPassTarget(player, "cross");
            if (crossTarget) this.passBall(player, crossTarget);
          } else if (shootWindow && this.rand() > 0.46 * profile.shortPassBias) {
            this.shootBall(
              player,
              player.team === "home" ? this.width + 30 : -30,
              this.height / 2 + (this.rand() * 180 - 90),
              24 + context.intensity * 6 + profile.verticality * 2,
            );
          } else {
            const teammate = this.bestPassTarget(player, "build");
            if (teammate) this.passBall(player, teammate);
          }
        }
      } else if (!holder) {
        const sameTeamClosest = this.closestPlayer(this.ball.x, this.ball.y, player.team);
        const chaseRadius = 110 + profile.press * 60;
        if (sameTeamClosest === player || Math.hypot(player.x - this.ball.x, player.y - this.ball.y) < chaseRadius) {
          player.tx = this.ball.x + teamDirection * 10;
          player.ty = this.ball.y + lateralDrift * 0.25;
        } else {
          player.tx = shapeX;
          player.ty = shapeY + lateralDrift * 0.35;
        }
      } else if (holder.team === player.team) {
        if (this.isStrikerRole(player.role)) {
          player.tx = this.clamp(
            holder.x + teamDirection * (120 + profile.support * 48),
            60,
            this.width - 60,
          );
          player.ty = this.clamp(shapedY + lateralDrift * (1.2 + profile.breakaway * 0.18), 90, this.height - 90);
        } else if (player.role === "cam") {
          player.tx = this.clamp(holder.x + teamDirection * (58 + profile.support * 26), 72, this.width - 72);
          player.ty = this.clamp(this.height / 2 + laneFromCenter * 0.6 + lateralDrift * 0.55, 96, this.height - 96);
        } else if (this.isWideRole(player.role)) {
          player.tx = this.clamp(shapeX + teamDirection * (66 + profile.wideBias * 32), 40, this.width - 40);
          player.ty = this.clamp(shapedY + lateralDrift, 70, this.height - 70);
        } else if (this.isBackLineRole(player.role)) {
          player.tx = this.clamp(shapeX - teamDirection * (18 - teamTilt * 36), 50, this.width - 50);
          player.ty = this.clamp(shapeY, 78, this.height - 78);
        } else {
          player.tx = this.clamp(shapeX + teamDirection * (32 + profile.support * 14), 54, this.width - 54);
          player.ty = this.clamp(shapeY, 80, this.height - 80);
        }
      } else {
        const primaryPresser = this.closestPlayer(holder.x, holder.y, player.team);
        const pressRange = 300 + profile.press * 170;
        if (primaryPresser === player && Math.hypot(player.x - holder.x, player.y - holder.y) < pressRange) {
          player.tx = holder.x - teamDirection * (10 + profile.press * 6);
          player.ty = holder.y;
        } else {
          const recoveryDepth = this.isBackLineRole(player.role) ? 70 : 48;
          player.tx = this.clamp(
            shapeX - teamDirection * (recoveryDepth + (1 - profile.depth) * 70 - teamTilt * 38),
            48,
            this.width - 48,
          );
          player.ty = this.clamp(shapeY, 76, this.height - 76);
        }
      }

      this.movePlayer(player, speedMultiplier);

      if (this.ball.attachedTo === player) {
        const dribbleOffset = player.team === "home" ? 16 : -16;
        this.ball.x = player.x + dribbleOffset;
        this.ball.y = player.y + Math.sin(timestamp / 60 + player.stride) * 6;
        this.ball.z = 0;
      }
    }
  }

  updateIdleState(timestamp) {
    for (const player of this.players) {
      if (this.matchState === "prematch") {
        player.tx = player.baseX * this.width;
        player.ty = player.baseY * this.height + Math.sin(timestamp / 500 + player.stride) * 8;
      } else {
        const driftX = Math.cos(timestamp / 820 + player.stride + player.slot) * 10;
        const driftY = Math.sin(timestamp / 760 + player.stride) * 8;
        player.tx = player.baseX * this.width + driftX;
        player.ty = player.baseY * this.height + driftY;
      }
      this.movePlayer(player, this.matchState === "prematch" ? 0.65 : 0.55);
    }

    this.ball.attachedTo = null;
    this.ball.x = this.width / 2;
    this.ball.y = this.height / 2;
    this.ball.vx = 0;
    this.ball.vy = 0;
    this.ball.z = 0;
    this.ball.vz = 0;
  }

  updateStoppage(timestamp) {
    if (!this.sequence) {
      this.matchState = "playing";
      return;
    }

    if (timestamp >= this.sequence.expiresAt) {
      this.matchState = this.liveState.status === "live" ? "playing" : this.normalizeStatus(this.liveState.status);
      const restartPlayer = this.closestPlayer(this.sequence.anchorX, this.sequence.anchorY, this.sequence.team) || this.pickKickoffPlayer(this.sequence.team);
      this.ball.attachedTo = restartPlayer;
      if (restartPlayer) {
        this.ball.x = restartPlayer.x;
        this.ball.y = restartPlayer.y;
      }
      this.sequence = null;
      return;
    }

    const attackDirection = this.sequence.team === "home" ? 1 : -1;
    const wallX = this.sequence.anchorX + attackDirection * 84;

    for (const player of this.players) {
      if (player.team === this.sequence.team) {
        if (this.isStrikerRole(player.role) || player.role === "cam" || player.role === "cm" || this.isWideRole(player.role)) {
          player.tx = this.sequence.anchorX - attackDirection * (30 + player.slot * 6);
          player.ty = this.sequence.anchorY + Math.sin(player.stride + player.slot) * 70;
        } else {
          player.tx = player.baseX * this.width;
          player.ty = player.baseY * this.height;
        }
      } else if (player.role === "gk") {
        player.tx = player.baseX * this.width;
        player.ty = this.height / 2;
      } else {
        player.tx = wallX;
        player.ty = this.sequence.anchorY - 120 + (player.slot % 5) * 48;
      }
      this.movePlayer(player, 0.72);
    }

    this.ball.attachedTo = null;
    this.ball.x = this.sequence.anchorX;
    this.ball.y = this.sequence.anchorY;
    this.ball.z = 0;
    this.ball.vx = 0;
    this.ball.vy = 0;
  }

  updateGoalCelebration(timestamp) {
    if (!this.sequence) {
      this.matchState = "playing";
      return;
    }

    const scorer = this.sequence.scorer;
    if (!scorer) {
      this.matchState = "playing";
      this.sequence = null;
      return;
    }

    if (!this.sequence.shotFired && timestamp >= this.sequence.shotAt) {
      this.sequence.shotFired = true;
      this.shootBall(scorer, this.sequence.targetX, this.sequence.targetY, 42);
    }

    if (this.sequence.shotFired) {
      this.updateBallPhysics(this.sequence.team);
    } else {
      this.ball.attachedTo = scorer;
      this.ball.x = scorer.x + (this.sequence.team === "home" ? 18 : -18);
      this.ball.y = scorer.y;
      this.ball.z = 0;
    }

    for (const player of this.players) {
      if (player.team === this.sequence.team) {
        if (player === scorer || this.isStrikerRole(player.role) || this.isWideRole(player.role) || player.role === "cam") {
          player.tx = this.sequence.celebrationX + Math.cos(player.stride + player.slot) * 70;
          player.ty = this.sequence.celebrationY + Math.sin(player.stride + player.slot) * 52;
        } else {
          player.tx = player.baseX * this.width + (this.sequence.team === "home" ? 70 : -70);
          player.ty = player.baseY * this.height;
        }
      } else {
        player.tx = player.baseX * this.width;
        player.ty = player.baseY * this.height;
      }
      this.movePlayer(player, player.team === this.sequence.team ? 1.22 : 0.84);
    }

    if (timestamp >= this.sequence.expiresAt) {
      const nextKickoff = this.otherTeam(this.sequence.team);
      this.sequence = null;
      this.resetForKickoff(nextKickoff);
      this.matchState = this.liveState.status === "live" ? "playing" : "prematch";
    }
  }

  drawPitch(timestamp) {
    this.ctx.fillStyle = this.pitchPattern;
    this.ctx.fillRect(0, 0, this.width, this.height);

    this.ctx.fillStyle = "rgba(255, 255, 255, 0.045)";
    for (let stripe = 0; stripe < 12; stripe += 1) {
      this.ctx.fillRect(0, stripe * 90, this.width, 46);
    }

    const context = this.deriveContext();
    const emphasis = Math.abs(context.homeTilt) * 0.26;
    if (emphasis > 0.02) {
      const attackGradient = this.ctx.createLinearGradient(0, 0, this.width, 0);
      attackGradient.addColorStop(
        0,
        context.homeTilt > 0 ? "rgba(0, 176, 255, 0.02)" : `rgba(255, 215, 64, ${emphasis})`,
      );
      attackGradient.addColorStop(0.5, "rgba(255, 255, 255, 0.01)");
      attackGradient.addColorStop(
        1,
        context.homeTilt > 0 ? `rgba(0, 176, 255, ${emphasis})` : "rgba(255, 215, 64, 0.02)",
      );
      this.ctx.fillStyle = attackGradient;
      this.ctx.fillRect(0, 0, this.width, this.height);
    }

    this.ctx.strokeStyle = "rgba(255,255,255,0.7)";
    this.ctx.lineWidth = 4;
    this.ctx.strokeRect(20, 20, this.width - 40, this.height - 40);
    this.ctx.beginPath();
    this.ctx.moveTo(this.width / 2, 20);
    this.ctx.lineTo(this.width / 2, this.height - 20);
    this.ctx.stroke();
    this.ctx.beginPath();
    this.ctx.arc(this.width / 2, this.height / 2, 110, 0, Math.PI * 2);
    this.ctx.stroke();
    this.ctx.strokeRect(20, this.height / 2 - 170, 180, 340);
    this.ctx.strokeRect(this.width - 200, this.height / 2 - 170, 180, 340);
    this.ctx.strokeRect(20, this.height / 2 - 70, 56, 140);
    this.ctx.strokeRect(this.width - 76, this.height / 2 - 70, 56, 140);

    if (this.visualPulse.strength > 0.02) {
      const pulseX = this.ball.x || this.width / 2;
      const pulseY = this.ball.y || this.height / 2;
      const color = this.visualPulse.team === "away" ? "255, 215, 64" : "0, 176, 255";
      const pulse = this.ctx.createRadialGradient(pulseX, pulseY, 0, pulseX, pulseY, 340);
      pulse.addColorStop(0, `rgba(${color}, ${0.22 * this.visualPulse.strength})`);
      pulse.addColorStop(1, "rgba(0,0,0,0)");
      this.ctx.fillStyle = pulse;
      this.ctx.fillRect(0, 0, this.width, this.height);
    }

    if (this.weatherFx.raining) {
      this.ctx.strokeStyle = "rgba(183, 221, 255, 0.32)";
      this.ctx.lineWidth = 2;
      this.weatherFx.rain.forEach((drop) => {
        this.ctx.beginPath();
        this.ctx.moveTo(drop.x, drop.y);
        this.ctx.lineTo(drop.x + this.weatherFx.wind * 50, drop.y + drop.length);
        this.ctx.stroke();
      });
    }

    const dormantVeil = {
      halftime: 0.08,
      fulltime: 0.12,
      stale: 0.2,
      offline: 0.28,
      waiting: 0.22,
    }[this.matchState] || 0;

    if (dormantVeil > 0) {
      this.ctx.fillStyle = `rgba(5, 10, 16, ${dormantVeil})`;
      this.ctx.fillRect(0, 0, this.width, this.height);
    }
  }

  drawPlayer(player, timestamp) {
    const moving = Math.hypot(player.tx - player.x, player.ty - player.y) > 3;
    const bobble = moving ? Math.abs(Math.sin(timestamp / 120 + player.stride)) * 8 : 0;
    const angle = moving
      ? Math.atan2(player.ty - player.y, player.tx - player.x)
      : (player.team === "home" ? 0 : Math.PI);
    const palette = this.getPlayerPalette(player);
    const facing = this.spriteFacing(angle);
    const direction = facing === "up" ? "up" : facing === "down" ? "down" : "side";
    const mirrored = facing === "left";
    const frame = moving ? Math.floor(timestamp / 150) % 2 : 0;
    const spriteWidth = 8 * 5;
    const spriteHeight = 12 * 5;
    const originX = Math.round(player.x - spriteWidth / 2);
    const originY = Math.round(player.y - spriteHeight / 2 - bobble);

    this.ctx.fillStyle = "rgba(0,0,0,0.24)";
    this.ctx.beginPath();
    this.ctx.ellipse(player.x, player.y + 18, 20, 8, 0, 0, Math.PI * 2);
    this.ctx.fill();

    if (this.ball.attachedTo === player) {
      this.ctx.strokeStyle = player.aura;
      this.ctx.lineWidth = 3;
      this.ctx.beginPath();
      this.ctx.arc(player.x, player.y + 4, 24, 0, Math.PI * 2);
      this.ctx.stroke();
    }
    this.paintPixelSprite(originX, originY, palette, direction, frame, mirrored, this.isGoalkeeperRole(player.role));

    if (this.ball.attachedTo === player) {
      this.ctx.fillStyle = palette.pointer;
      this.ctx.beginPath();
      this.ctx.moveTo(player.x, originY - 10);
      this.ctx.lineTo(player.x - 7, originY + 2);
      this.ctx.lineTo(player.x + 7, originY + 2);
      this.ctx.closePath();
      this.ctx.fill();
    }
  }

  drawBall() {
    const moving = !this.ball.attachedTo && (Math.abs(this.ball.vx) + Math.abs(this.ball.vy) > 1.8 || this.ball.z > 1);

    if (moving) {
      this.ctx.strokeStyle = "rgba(255,255,255,0.22)";
      this.ctx.lineWidth = 4;
      this.ctx.beginPath();
      this.ctx.moveTo(this.ball.x - this.ball.vx * 1.6, this.ball.y - this.ball.vy * 1.6);
      this.ctx.lineTo(this.ball.x, this.ball.y);
      this.ctx.stroke();
    }

    this.ctx.fillStyle = "rgba(0,0,0,0.32)";
    this.ctx.beginPath();
    this.ctx.arc(this.ball.x, this.ball.y + 12, 6, 0, Math.PI * 2);
    this.ctx.fill();

    this.ctx.fillStyle = "#ffffff";
    this.ctx.beginPath();
    this.ctx.arc(this.ball.x, this.ball.y - this.ball.z, 9, 0, Math.PI * 2);
    this.ctx.fill();
    this.ctx.strokeStyle = "rgba(0,0,0,0.3)";
    this.ctx.lineWidth = 2;
    this.ctx.stroke();
    this.ctx.fillStyle = "rgba(12, 16, 24, 0.22)";
    this.ctx.beginPath();
    this.ctx.arc(this.ball.x + 2, this.ball.y - this.ball.z - 1, 3.2, 0, Math.PI * 2);
    this.ctx.fill();
  }

  draw(timestamp) {
    this.drawPitch(timestamp);

    const entities = [...this.players, this.ball].sort((left, right) => left.y - right.y);
    for (const entity of entities) {
      if (entity === this.ball) {
        this.drawBall();
      } else {
        this.drawPlayer(entity, timestamp);
      }
    }
  }
}

window.onload = () => {
  window.swosEngine = new SWOSEngine("pitch");
};
