# AVA Games Database

Live maps of Call of War games (Europe Clash of Nations), updated automatically, with an overview page of all live and saved games. Everything runs on GitHub: once it is set up you do not need your PC or Claude.

---

## Setup guide (one time, about 15 minutes)

### What you need

- A **GitHub account** (free): <https://github.com/signup>
- **GitHub Desktop** (free, easiest way to upload the files): <https://desktop.github.com>
- Your **Call of War username and password** (the account that can see the game)
- This folder, unzipped (`ava-database`)

### Step 1 – Create the repository

1. Go to <https://github.com/new>.
2. **Repository name:** for example `ava-maps`. This name becomes part of your website address.
3. Choose **Public**. (GitHub Pages and the automatic updates are free and unlimited for public repositories. Anyone with the link can view the maps, but only you can change anything.)
4. Leave *Add a README*, *.gitignore* and *license* **unticked** (this folder already has them).
5. Click **Create repository**.

### Step 2 – Upload the files with GitHub Desktop

1. Open GitHub Desktop and sign in with your GitHub account (*File → Options → Accounts*).
2. **File → Add local repository…** → choose the unzipped `ava-database` folder.
3. GitHub Desktop says *"This directory does not appear to be a Git repository"* → click **create a repository** → then **Create repository** (keep the defaults).
4. Click **Publish repository** (top bar).
   - **Name:** the same name as in step 1 (`ava-maps`).
   - **Untick** *Keep this code private*.
   - Click **Publish repository**.
   - If it says the repository already exists: use *Repository → Repository settings → Remote* and paste `https://github.com/YOUR-NAME/ava-maps.git`, then click **Push origin**.
5. Refresh your repository page on github.com: you should see the folders `.github`, `games`, `map`, `scripts` and this README.

> Files that are **not** uploaded on purpose (listed in `.gitignore`): `node_modules/`, `.env` (your password), `site/` (built by GitHub itself) and `game_data.json` (fetched by GitHub itself).

<details>
<summary>Alternative without GitHub Desktop (upload in the browser)</summary>

On the empty repository page click **uploading an existing file**. Drag in the *contents* of the `ava-database` folder (not the folder itself) and click **Commit changes**. The browser accepts at most 100 files per upload, so upload `map/icons` (100 icons) in a second round via *Add file → Upload files* inside the `map/icons` folder. Check that the hidden folder **`.github`** was uploaded too; if not, create the file `.github/workflows/update.yml` via *Add file → Create new file* and paste its contents.
</details>

### Step 3 – Add your Call of War login as secrets

GitHub keeps these encrypted; nobody (not even people who view the repository) can read them.

1. In your repository: **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**:
   - Name: `COW_USERNAME` – Secret: your Call of War username → **Add secret**
3. Click **New repository secret** again:
   - Name: `COW_PASSWORD` – Secret: your Call of War password → **Add secret**

### Step 4 – Allow the robot to save its work

1. **Settings → Actions → General**.
2. Under **Actions permissions**: *Allow all actions and reusable workflows* (the default).
3. Scroll down to **Workflow permissions** → choose **Read and write permissions** → **Save**.

### Step 5 – Turn on the website (GitHub Pages)

1. **Settings → Pages**.
2. **Source:** choose **GitHub Actions**.

### Step 6 – First run

1. Go to the **Actions** tab. If GitHub asks, click **I understand my workflows, go ahead and enable them**.
2. Click **Update maps** (left) → **Run workflow** (right) → keep *update* → **Run workflow**.
3. Wait 3–5 minutes. Click the run to follow it.
   - A **green tick** means it worked. Open the step *Fetch and build* and check that it says `[SUCCESS]`.
   - A **red cross**: click the red step, copy the error text and send it to whoever helps you (or Claude).
4. Your site is now at **`https://YOUR-NAME.github.io/ava-maps/`** (also shown under *Settings → Pages* and in the *deploy* step of the run).

> **Not tested yet:** whether Call of War allows logging in from GitHub's servers. If the log shows a login error, your PC can keep doing the fetching (see *Running on your PC*) while GitHub builds and hosts the site.

### Step 7 – Done

From now on GitHub checks every quarter of an hour which games are due and updates them on the whole hour (or half hour, etc.). You can close your PC.

---

## Using the website

### Add a game
On the overview page, type the game code under **New map** and click **Create**. GitHub opens a filled-in form: click **Submit new issue**. Within a few minutes the map appears under *Live maps*.

### How often a map is updated
Every map has **Update every** at the top right: 15 min, 30 min, 1 hour (default), 2 hours or 4 hours. Choosing a value opens a filled-in GitHub form: click **Submit new issue** and the new pace applies from the next round.

- Updates happen at whole moments in Amsterdam time: *1 hour* = 01:00, 02:00, …; *30 min* = :00 and :30; *15 min* = :00, :15, :30, :45; *2 hours* = 00:00, 02:00, 04:00, …; *4 hours* = 00:00, 04:00, 08:00, ….
- The robot runs every quarter of an hour but only fetches the games whose moment has come; when nothing is due it stops after a few seconds. If GitHub skips a round, the next one catches up.
- GitHub often starts scheduled runs a few minutes late (especially on the whole hour), so an update planned for 02:00 may appear at 02:05–02:15.
- *Actions → Update maps → Run workflow* always updates all live games immediately.

### Stop, move or delete a game
- **Stop** (live game): asks *Are you sure?* and lets you pick one or more folders. The game moves to *Saved games* with everything up to now and stops updating. A game that ends (winner known) is saved automatically.
- **Folders:** under *Saved games*, **+ New folder** makes a folder. **📁 Folders** next to a saved game lets you tick every folder it should be in (a game can be in several folders at once) or type a new one. **delete** next to a folder removes only the folder (its games stay in their other folders, or go back to *Unsorted*).
- These requests only change the list and the overview page; they do **not** fetch or update the live games.
- **Delete** (saved game): asks twice, then removes the game, its map and its whole history for good. Stop a live game first.

Only members of the repository can do these things; requests from anyone else are ignored.

### Fixing a wrong unit type
The game's newspaper names a fleet after one ship type, which is not always right (e.g. reported as *Cruiser* while it is battleships). Add a correction to `games/<code>/unit_fix.json`, for example:

```json
{ "E1": { "from": "Cruiser", "to": "Battleship" } }
```

`E1` is the unit code as shown on the map. Edit the file on github.com (pencil icon → **Commit changes**); the next update uses it.

---

## How it works

| Part | File | What it does |
|---|---|---|
| Game list | `games.json` | Per game: code, name, status (`live` / `saved`), update interval, folder and the latest score |
| Fetcher | `scripts/fetch.js` | Logs in to Call of War and downloads the game state → `games/<code>/game_data.json` |
| Newspaper keeper | `scripts/import_news.py` | Stores captures, revolts and destroyed units in `games/<code>/gd_events.json` (the game's own newspaper only keeps ~24 hours) |
| Map builder | `scripts/build_game.py` | Builds the Live AVA viewer of one game → `site/games/<code>/index.html` |
| Overview | `scripts/build_site.py` | Builds the start page → `site/index.html` |
| One round | `scripts/run.py` | All of the above for every game that is due; a finished game moves to *Saved games* |
| List changes | `scripts/manage.py` | Add / stop / move / delete games, folders and update intervals |
| Automation | `.github/workflows/update.yml` | Runs every quarter of an hour (:00, :15, :30, :45) and on requests from the website, then publishes the site |

`map/` holds the map itself (background, 634 provinces with exact borders, 140 cities, unit icons) and is the same for every game. `games/<code>/` holds the collected history of one game. Saved games keep their final page in `archive/<code>.html`.

Everything from **day 2, 18:00** is shown; day 1 is not.

## Settings (`config.json`)

- `title`: name at the top of the overview page
- `timezone`: time zone for all times (default `Europe/Amsterdam`)
- `repo`: `user/repository` on GitHub. **Leave empty**: on GitHub the site fills it in by itself. Only needed when you open the site locally and want the buttons to work.

To change how often GitHub *checks* (not how often a map updates), edit the `cron` line in `.github/workflows/update.yml`. Times there are in UTC.

## Running on your PC

Needed: Node.js and Python 3.

```
npm install
pip install -r requirements.txt
copy .env.example .env          (then fill in your username and password)
python scripts/run.py           (fetch + build everything; then open site/index.html)
python scripts/run.py --no-fetch   (only rebuild)
```

- **Test with another game:** double-click `test_game.bat` and type the game code.
- **Update on your PC:** double-click `update_local.bat`.
- **Command line:** `python scripts/manage.py add 10917564 "KH vs PHK"`, `... stop 10917564 "Season 1"`, `... move 10917564 "Season 1; Finals"`, `... every 10917564 30`.

## Troubleshooting

| Problem | Fix |
|---|---|
| Run fails at *Fetch and build* with a login error | Check the two secrets (step 3). If they are right, Call of War may block GitHub's servers: fetch on your PC instead. |
| Run fails at *Save history* with "Permission denied" / 403 | Step 4: set *Read and write permissions*. |
| *deploy* step fails | Step 5: *Settings → Pages → Source: GitHub Actions*. |
| Buttons say "Not connected to GitHub yet" | You opened the page locally; on the GitHub site this works by itself. |
| The form opens but nothing happens | Only repository members count. Check the *Actions* tab for the run; the issue gets a comment when it is done or failed. |
| Scheduled runs stopped | GitHub pauses schedules after 60 days without commits; the bot commits on every update, so this only happens when no game is live. Run the workflow once by hand to wake it up. |
