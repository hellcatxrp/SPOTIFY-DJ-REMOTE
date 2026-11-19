# Spotify DJ

Type a request in Claude. A small program on your computer plays it on Spotify.

The same instructions are on one page in [Spotify-DJ-Setup.pdf](Spotify-DJ-Setup.pdf).

You need Spotify Premium on the account you listen with, the Claude desktop app from [claude.com/download](https://claude.com/download), and Python 3.11 or newer from [python.org](https://www.python.org/downloads/) with **Add python.exe to PATH** ticked.

`127.0.0.1` means "this computer." It is the same address for everyone. It is not a public IP.

Each person creates their own Spotify app. `.env` and `.spotify_token_cache` stay on your machine.

## 1. Create a Spotify app

Open [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and log in with the Spotify account you listen on. Create an app named **Spotify DJ**. Set the redirect URI to:

```
http://127.0.0.1:8888/callback
```

If the create form has no URI field, open the app's Settings afterward, add it there, and save. Copy the Client ID. Reveal and copy the Client Secret. Development mode is enough. If a different Spotify account will be the one listening, add that account under the app's user list.

Spotify rejects `localhost`. The address has to be `127.0.0.1`, and it has to match `.env` character for character.

## 2. Save your keys

```powershell
copy .env.example .env
notepad .env
```

Replace `your_client_id` and `your_client_secret` with the values from the dashboard. Leave the redirect line as it is.

## 3. Install and sign in once

In PowerShell, from this folder. If `py` is not recognized, use `python` in place of `py -3`.

```powershell
py -3 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe spotify_dj.py --auth
```

A browser opens. Approve access. PowerShell should print **Signed in as** your Spotify name. That writes `.spotify_token_cache` beside the script.

## 4. Prove a song plays before involving Claude

Open Spotify on this PC, the web player, or your phone, and let any track start so Spotify has a live device. Then:

```powershell
.\venv\Scripts\python.exe spotify_dj.py --test "artist and song"
```

That track should start, and the window should say **Playing track**. If it says **No Spotify device found**, play a second of audio and run the test again.

## 5. Tell Claude Desktop to start it

Open **Settings → Developer → Edit Config**. On a newer layout the same control is under Settings → Desktop app.

If the file is empty, paste the block below. If it already has an `mcpServers` section, add only the `spotify-dj` entry inside it and leave every other line in place. Change both paths to your folder. Copy the slashes as they are.

```json
{
  "mcpServers": {
    "spotify-dj": {
      "command": "C:/Users/You/spotify-dj/venv/Scripts/python.exe",
      "args": ["C:/Users/You/spotify-dj/spotify_dj.py"]
    }
  }
}
```

Save. Quit Claude from the system tray icon, then open it again. Developer settings should list **spotify-dj** as connected.

If you installed Claude from the Microsoft Store and the server never appears, put the same block in `claude_desktop_config.json` in this folder, then quit from the tray again:

```
%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\
```

## 6. Request music in plain text

Open a new chat:

- Play Blonde by Frank Ocean.
- Queue Pink + White and set the volume to 40.
- What's playing?
- Skip. Pause. Play this on my phone.

Claude searches your Spotify and starts the top match: a track, album, playlist, or artist. Spotify has to be open somewhere that account is logged in.

You are finished when a new Claude chat can start a song you name, without you touching Spotify.

## If it fails

A 403 means the listening account needs Premium. Run `--auth` again after that. A redirect error means the dashboard URI and `.env` disagree. If Claude cannot find the remote, the path in the config is wrong, or Claude is still running in the tray. Logs are in `%APPDATA%\Claude\logs`, or in the logs folder next to the Store config above.

On a Mac the steps are the same. Use `python3` and `./venv/bin/python`, and point `command` at that python.

## What Claude can do

Play a track, album, playlist, or artist. Queue a track. Pause, resume, skip, go back. Set volume. Say what is playing. List devices and move playback to another one.
