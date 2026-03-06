/**
 * SWOS420 HTML5 Canvas Visualizer Engine
 *
 * A broadcast-oriented 2D match visualizer that consumes live stream state
 * from overlay.html and reacts to scorelines, match phases, and structured
 * commentary events.
 */

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
    this.possessionTeam = "home";
    this.sequence = null;
    this.visualPulse = { type: "", team: null, strength: 0, expiresAt: 0 };
    this.weatherFx = { raining: false, rain: [], wind: 0 };
    this.liveState = {
      status: "waiting",
      minute: 0,
      homeGoals: 0,
      awayGoals: 0,
      homeTeam: "Home",
      awayTeam: "Away",
      weather: "dry",
      story: "",
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

  otherTeam(team) {
    return team === "away" ? "home" : "away";
  }

  normalizeStatus(status) {
    const normalized = String(status || "waiting").toLowerCase();
    if (normalized === "ft") return "fulltime";
    if (normalized === "ht") return "halftime";
    if (normalized === "live" || normalized === "prematch" || normalized === "halftime" || normalized === "fulltime") {
      return normalized;
    }
    return "waiting";
  }

  loadAssets() {
    const urls = {
      pitch: "assets/pitch_tile.png",
      spritesheet: "assets/spritesheet.png",
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
      speed: 2.2 + Math.random() * 1.2,
      stride: Math.random() * Math.PI * 2,
      aura: team === "home" ? "rgba(0, 176, 255, 0.26)" : "rgba(255, 215, 64, 0.28)",
    };
  }

  createRainDrop() {
    return {
      x: Math.random() * this.width,
      y: Math.random() * this.height,
      speed: 18 + Math.random() * 16,
      length: 18 + Math.random() * 20,
    };
  }

  configureWeather(weather) {
    const weatherText = String(weather || "").toLowerCase();
    const raining = /(rain|wet|storm)/.test(weatherText);
    this.weatherFx.raining = raining;
    this.weatherFx.wind = /(wind|storm)/.test(weatherText)
      ? (Math.random() < 0.5 ? -1 : 1) * (0.08 + Math.random() * 0.08)
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

    const formation = [
      { x: 0.1, y: 0.5, role: "gk" },
      { x: 0.24, y: 0.2, role: "lb" },
      { x: 0.2, y: 0.38, role: "cb" },
      { x: 0.2, y: 0.62, role: "cb" },
      { x: 0.24, y: 0.8, role: "rb" },
      { x: 0.38, y: 0.18, role: "lm" },
      { x: 0.34, y: 0.4, role: "cm" },
      { x: 0.34, y: 0.6, role: "cm" },
      { x: 0.38, y: 0.82, role: "rm" },
      { x: 0.48, y: 0.42, role: "st" },
      { x: 0.48, y: 0.58, role: "st" },
    ];

    formation.forEach((anchor, index) => {
      this.players.push(this.buildPlayer("home", anchor, index));
    });
    formation.forEach((anchor, index) => {
      this.players.push(this.buildPlayer("away", anchor, index));
    });

    this.configureWeather(this.liveState.weather);
    this.resetForKickoff("home");
    this.matchState = "prematch";
  }

  pickKickoffPlayer(team) {
    return this.players.find((player) => player.team === team && player.role === "st")
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

    this.liveState = {
      ...this.liveState,
      ...snapshot,
      status,
      latestEvent,
    };

    this.configureWeather(this.liveState.weather);

    if (!this.players.length) return;

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
    }
  }

  startStoppage(kind, attackingTeam, durationMs) {
    if (this.matchState === "goal_celebration") return;

    const anchorX = this.width * (attackingTeam === "home" ? 0.68 : 0.32);
    const anchorY = this.height * (0.35 + Math.random() * 0.3);
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
    striker.y = this.height * (0.36 + Math.random() * 0.28);
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
      celebrationY: this.height * (0.2 + Math.random() * 0.6),
      targetX: scorerTeam === "home" ? this.width + 24 : -24,
      targetY: this.height / 2 + (Math.random() * 180 - 90),
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

    let homeTilt = 0;
    if (scoreDiff < 0) homeTilt += 0.28 + lateFactor * 0.24;
    if (scoreDiff > 0) homeTilt -= 0.14 * lateFactor;
    if (this.possessionTeam === "home") homeTilt += 0.08;
    if (this.possessionTeam === "away") homeTilt -= 0.08;
    if (this.liveState.latestEvent?.team === "home") homeTilt += this.visualPulse.strength * 0.2;
    if (this.liveState.latestEvent?.team === "away") homeTilt -= this.visualPulse.strength * 0.2;
    homeTilt = this.clamp(homeTilt, -0.55, 0.55);

    return {
      minute,
      scoreDiff,
      lateFactor,
      homeTilt,
      intensity: this.clamp(0.78 + lateFactor * 0.38 + this.visualPulse.strength * 0.2, 0.72, 1.45),
      homeUrgency: scoreDiff < 0 ? 1.1 + lateFactor * 0.5 : scoreDiff > 0 ? 0.84 - lateFactor * 0.2 : 1,
      awayUrgency: scoreDiff > 0 ? 1.1 + lateFactor * 0.5 : scoreDiff < 0 ? 0.84 - lateFactor * 0.2 : 1,
      focusTeam: this.ball.attachedTo?.team || this.possessionTeam || (homeTilt >= 0 ? "home" : "away"),
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
        drop.x = Math.random() * this.width;
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

    if (this.matchState === "halftime" || this.matchState === "fulltime" || this.matchState === "prematch" || this.matchState === "waiting") {
      this.updateIdleState(timestamp);
      return;
    }

    this.updateOpenPlay(timestamp);
  }

  roleWeight(role) {
    return {
      gk: -0.55,
      cb: -0.28,
      lb: -0.08,
      rb: -0.08,
      cm: 0.04,
      lm: 0.14,
      rm: 0.14,
      st: 0.28,
    }[role] ?? 0;
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
    this.ball.vz = 8 + Math.random() * 4;
  }

  passBall(player, teammate) {
    this.ball.attachedTo = null;
    const angle = Math.atan2(teammate.y - player.y, teammate.x - player.x);
    const distance = Math.hypot(teammate.y - player.y, teammate.x - player.x);
    const power = this.clamp(distance / 18, 12, 26);
    this.ball.vx = Math.cos(angle) * power;
    this.ball.vy = Math.sin(angle) * power;
    this.ball.vz = 3 + Math.random() * 2;
  }

  bestPassTarget(player) {
    const candidates = this.players
      .filter((candidate) => candidate.team === player.team && candidate !== player)
      .sort((left, right) => {
        if (player.team === "home") return right.x - left.x;
        return left.x - right.x;
      });
    return candidates[Math.floor(Math.random() * Math.max(1, Math.min(4, candidates.length)))];
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
      const baseX = player.baseX * this.width;
      const baseY = player.baseY * this.height;
      const teamDirection = player.team === "home" ? 1 : -1;
      const teamTilt = player.team === "home" ? context.homeTilt : -context.homeTilt;
      const roleWeight = this.roleWeight(player.role);
      const lateralDrift = Math.sin(timestamp / 520 + player.stride) * 24;
      const shapeX = baseX
        + (this.ball.x - this.width / 2) * 0.12
        + teamDirection * (teamTilt * (150 + roleWeight * 140));
      const shapeY = baseY + (this.ball.y - this.height / 2) * 0.18;
      const speedMultiplier = context.intensity * (player.team === "home" ? context.homeUrgency : context.awayUrgency);

      if (this.ball.attachedTo === player) {
        const targetX = player.team === "home" ? this.width - 120 : 120;
        const targetY = this.clamp(player.y + Math.sin(timestamp / 300 + player.stride) * 56, 90, this.height - 90);
        player.tx = targetX;
        player.ty = targetY;

        const distanceToGoal = Math.hypot(player.x - targetX, player.y - this.height / 2);
        const urgent = player.team === "home" ? context.homeUrgency : context.awayUrgency;
        const actionRate = 0.01 * context.intensity * urgent * (player.role === "st" ? 1.6 : 1);

        if (Math.random() < actionRate) {
          if (distanceToGoal < 380 || (context.lateFactor > 0.76 && urgent > 1)) {
            this.shootBall(
              player,
              player.team === "home" ? this.width + 30 : -30,
              this.height / 2 + (Math.random() * 180 - 90),
              24 + context.intensity * 6,
            );
          } else {
            const teammate = this.bestPassTarget(player);
            if (teammate) this.passBall(player, teammate);
          }
        }
      } else if (!holder) {
        const sameTeamClosest = this.closestPlayer(this.ball.x, this.ball.y, player.team);
        if (sameTeamClosest === player || Math.hypot(player.x - this.ball.x, player.y - this.ball.y) < 120) {
          player.tx = this.ball.x + teamDirection * 10;
          player.ty = this.ball.y + lateralDrift * 0.25;
        } else {
          player.tx = shapeX;
          player.ty = shapeY + lateralDrift * 0.35;
        }
      } else if (holder.team === player.team) {
        if (player.role === "st") {
          player.tx = this.clamp(holder.x + teamDirection * 160, 60, this.width - 60);
          player.ty = this.clamp(holder.y + lateralDrift * 1.6, 90, this.height - 90);
        } else if (player.role === "lm" || player.role === "rm" || player.role === "lb" || player.role === "rb") {
          player.tx = this.clamp(shapeX + teamDirection * 90, 40, this.width - 40);
          player.ty = this.clamp(baseY + lateralDrift, 70, this.height - 70);
        } else {
          player.tx = shapeX + teamDirection * 36;
          player.ty = shapeY;
        }
      } else {
        const primaryPresser = this.closestPlayer(holder.x, holder.y, player.team);
        if (primaryPresser === player && Math.hypot(player.x - holder.x, player.y - holder.y) < 520) {
          player.tx = holder.x - teamDirection * 12;
          player.ty = holder.y;
        } else {
          player.tx = shapeX - teamDirection * (60 - teamTilt * 70);
          player.ty = shapeY;
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
    const midpointX = this.width / 2;
    const midpointY = this.height / 2;

    for (const player of this.players) {
      const teamDirection = player.team === "home" ? -1 : 1;
      if (this.matchState === "prematch") {
        player.tx = player.baseX * this.width;
        player.ty = player.baseY * this.height + Math.sin(timestamp / 500 + player.stride) * 8;
      } else {
        player.tx = midpointX + teamDirection * 120 + Math.cos(player.stride + player.slot) * 120;
        player.ty = midpointY - 220 + (player.slot % 6) * 70;
      }
      this.movePlayer(player, this.matchState === "prematch" ? 0.65 : 0.55);
    }

    this.ball.attachedTo = null;
    this.ball.x = midpointX;
    this.ball.y = midpointY;
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
        if (player.role === "st" || player.role === "cm") {
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
        if (player === scorer || player.role === "st" || player.role === "lm" || player.role === "rm") {
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
  }

  drawPlayer(player, timestamp) {
    const moving = Math.hypot(player.tx - player.x, player.ty - player.y) > 3;
    const bobble = moving ? Math.abs(Math.sin(timestamp / 120 + player.stride)) * 8 : 0;
    const angle = Math.atan2(player.ty - player.y, player.tx - player.x);
    let row = 0;

    if (angle > -Math.PI / 4 && angle <= Math.PI / 4) row = 3;
    else if (angle > Math.PI / 4 && angle <= (3 * Math.PI) / 4) row = 1;
    else if (angle < -Math.PI / 4 && angle >= (-3 * Math.PI) / 4) row = 0;
    else row = 2;

    const frame = moving ? Math.floor(timestamp / 140) % 4 : 0;
    const fw = 16;
    const fh = 24;
    const sx = frame * fw;
    const sy = (row + (player.team === "home" ? 0 : 5)) * fh;
    const drawW = fw * this.scale;
    const drawH = fh * this.scale;

    this.ctx.fillStyle = "rgba(0,0,0,0.24)";
    this.ctx.beginPath();
    this.ctx.ellipse(player.x, player.y + 18, 20, 8, 0, 0, Math.PI * 2);
    this.ctx.fill();

    if (this.assets.spritesheet) {
      this.ctx.drawImage(
        this.assets.spritesheet,
        sx,
        sy,
        fw,
        fh,
        player.x - drawW / 2,
        player.y - drawH / 2 - bobble,
        drawW,
        drawH,
      );
    } else {
      this.ctx.fillStyle = player.team === "home" ? "#00b0ff" : "#ffd740";
      this.ctx.fillRect(player.x - 12, player.y - 28 - bobble, 24, 38);
    }

    if (this.ball.attachedTo === player) {
      this.ctx.strokeStyle = player.aura;
      this.ctx.lineWidth = 3;
      this.ctx.beginPath();
      this.ctx.arc(player.x, player.y + 4, 24, 0, Math.PI * 2);
      this.ctx.stroke();
    }
  }

  drawBall() {
    this.ctx.fillStyle = "rgba(0,0,0,0.32)";
    this.ctx.beginPath();
    this.ctx.arc(this.ball.x, this.ball.y + 12, 6, 0, Math.PI * 2);
    this.ctx.fill();

    if (this.assets.ball) {
      this.ctx.drawImage(this.assets.ball, this.ball.x - 16, this.ball.y - this.ball.z - 16, 32, 32);
    } else {
      this.ctx.fillStyle = "#fff";
      this.ctx.beginPath();
      this.ctx.arc(this.ball.x, this.ball.y - this.ball.z, 8, 0, Math.PI * 2);
      this.ctx.fill();
    }
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
