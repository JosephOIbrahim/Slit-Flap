# Using DEPARTURES when the command isn't enough

The README covers the normal path. This page holds the fallbacks.

## Restore by hand

Use this only if `departures restore` cannot run.

1. Stop the board. If it has no window (for example started from `departures-launch.vbs`), find the one using port 4040: `netstat -ano | findstr :4040` shows its PID on the `LISTENING` line, then `taskkill /PID <pid> /F`. Leave other Python programs alone.
2. Open the data folder. On Windows, paste `%DEPARTURES_HOME%` into File Explorer's address bar when that variable is set; otherwise paste `%USERPROFILE%\.departures`. On Mac and Linux, open `$DEPARTURES_HOME` when it is set, otherwise `~/.departures` (terminal: `cd "${DEPARTURES_HOME:-$HOME/.departures}"`). On Windows, turn on View → Show → File name extensions so you can see which file is which.
3. Make a folder in it called `before-restore` (if one is already there from an earlier restore, use `before-restore-2`, so its old `-wal` cannot be replayed onto the new board), and move `departures.db` into that folder together with `departures.db-wal` and `departures.db-shm` if they are there. Keep the three together: the `-wal` file can hold your latest changes, so together they are a complete copy of the board you are replacing.
4. Copy the backup you want from the `backups` folder into the data folder and rename the copy to `departures.db`. On Windows, check it did not become `departures.db.db`.
5. Start the board.

Do not leave `departures.db-wal` or `departures.db-shm` behind in step 3: they belong to the old board, and SQLite would replay them onto the restored one and corrupt it.

## Windows Firewall

If Windows asks whether to allow Python, allow it on private networks. To add the rule yourself:

```
netsh advfirewall firewall add rule name="Departures" dir=in action=allow protocol=TCP localport=4040
```

## Starting without a window

- `departures-launch.vbs` starts the board silently. Startup errors go to `launcher.log` in the data folder.
- `departures.bat` runs the copy of DEPARTURES in the repository and keeps a window open if the board fails.

Both pick a Python that can actually run the board: they try `python`, then `py -3.12`, then `py -3.11`, using the first one that can import the server.


## Build from a clone

You need Python 3.11+ and Node 18+.

| Tool | Check it | Get it |
|------|----------|--------|
| Python 3.11+ | `python --version` | [python.org/downloads](https://www.python.org/downloads/) |
| Node 18+ | `node --version` | [nodejs.org](https://nodejs.org/) |
| Git | `git --version` | [git-scm.com](https://git-scm.com/) |

```bash
git clone https://github.com/JosephOIbrahim/Slit-Flap.git
cd Slit-Flap
pip install -e .
cd frontend && npm install && npm run build && cd ..
departures
```

`departures/frontend/dist/` is gitignored, so the frontend build is required from a clone. Build once; after that, `departures` is the only command you need.
