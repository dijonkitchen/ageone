// A fresh sandbox per case and repetition: a copy of the repo (agent cases) or an empty
// directory (direct cases), with its own Git history so graders can diff against the start.
import { execFileSync, spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { ROOT } from "../../harness/config.mjs";

const GIT_ID = ["-c", "user.name=evals", "-c", "user.email=evals@localhost", "-c", "commit.gpgsign=false"];

export function git(cwd, ...args) {
  return execFileSync("git", [...GIT_ID, ...args], { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
}

export function repoCommit() {
  const commit = git(ROOT, "rev-parse", "HEAD");
  const dirty = git(ROOT, "status", "--porcelain").length > 0;
  return { commit, dirty };
}

export function loadCases(casesDir) {
  return readdirSync(casesDir, { withFileTypes: true })
    .filter((d) => d.isDirectory() && existsSync(join(casesDir, d.name, "case.json")))
    .map((d) => {
      const dir = join(casesDir, d.name);
      const def = JSON.parse(readFileSync(join(dir, "case.json"), "utf8"));
      if (def.id !== d.name) throw new Error(`${dir}: id ${def.id} does not match its folder`);
      return { mode: "agent", timeoutSec: 600, maxTurns: 40, needs: [], ...def, dir };
    })
    .sort((a, b) => a.id.localeCompare(b.id));
}

// Tracked and new files of the working tree, minus eval cases and results so no agent can read the graders,
// reference solutions, or earlier answers.
export function makeSandbox(runDir, caseDef, rep) {
  const dir = mkdtempSync(join(runDir, `${caseDef.id}-${rep}-`));
  const work = join(dir, "work");
  mkdirSync(work);
  if (caseDef.mode === "agent") {
    const files = git(ROOT, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
      .split("\0")
      .filter((f) => f && !/^evals\/(cases|results)\//.test(f) && existsSync(join(ROOT, f)));
    const tar = execFileSync("tar", ["-c", "--null", "-T", "-", "-f", "-"], { cwd: ROOT, input: files.join("\0"), maxBuffer: 1 << 30 });
    execFileSync("tar", ["-x", "-f", "-"], { cwd: work, input: tar });
  }
  git(work, "init", "-q", "-b", "main");
  git(work, "add", "-A");
  git(work, "commit", "-q", "--allow-empty", "-m", "base");
  if (existsSync(join(caseDef.dir, "setup.sh"))) {
    execFileSync("bash", [join(caseDef.dir, "setup.sh")], { cwd: work, env: scriptEnv(caseDef), stdio: "pipe" });
    git(work, "add", "-A");
    git(work, "commit", "-q", "--allow-empty", "-m", "setup");
  }
  return { dir, work, output: join(dir, "output.txt") };
}

// Setup, reference, and grader scripts get the case folder, the grader helpers (source "$EVALS_LIB/check.sh"),
// the repo root, and today's date.
export function scriptEnv(caseDef, extra = {}) {
  return {
    ...process.env,
    CASE_DIR: caseDef.dir,
    EVALS_LIB: join(ROOT, "evals", "lib"),
    REPO_ROOT: ROOT,
    EVAL_TODAY: new Date().toISOString().slice(0, 10),
    ...extra,
  };
}

// Run a command with a wall-clock limit, streaming stdout lines to onLine; `kill()` stops it early.
export function runProcess(cmd, args, { cwd, env, timeoutMs, onLine, input }) {
  return new Promise((resolve) => {
    const child = spawn(cmd, args, { cwd, env, stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    let buffered = "";
    let killedFor = null;
    const kill = (reason) => {
      if (killedFor) return;
      killedFor = reason;
      child.kill("SIGTERM");
      setTimeout(() => child.kill("SIGKILL"), 5000).unref();
    };
    const timer = setTimeout(() => kill("timeout"), timeoutMs);
    child.stdout.on("data", (chunk) => {
      const text = chunk.toString("utf8");
      stdout += text;
      if (!onLine) return;
      // Split on LF only: pi's JSON mode allows U+2028/U+2029 inside strings.
      buffered += text;
      let nl;
      while ((nl = buffered.indexOf("\n")) >= 0) {
        const line = buffered.slice(0, nl).replace(/\r$/, "");
        buffered = buffered.slice(nl + 1);
        if (line) onLine(line, kill);
      }
    });
    child.stderr.on("data", (chunk) => (stderr += chunk.toString("utf8")));
    child.on("error", (err) => {
      clearTimeout(timer);
      resolve({ code: -1, stdout, stderr: stderr + String(err), killedFor });
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (onLine && buffered.trim()) onLine(buffered.trim(), kill);
      resolve({ code, stdout, stderr, killedFor });
    });
    // A child may exit before reading its input; that is not an error.
    child.stdin.on("error", () => {});
    child.stdin.end(input ?? "");
  });
}
