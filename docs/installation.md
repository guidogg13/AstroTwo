# Installing AstroTwo

## Requirements

- **macOS 15 (Sequoia) or later**
- **Apple silicon** (M1 or later). Intel Macs are not supported.
- An internet connection for online surveys, catalogues and services. Files on your Mac (FITS images, catalogues, MOCs, saved sessions) open without a connection.
- Optional, for the AI assistant: an API key from a supported provider, or a local model in Ollama or LM Studio. See [the AI assistant](quickstart.md#9-the-ai-assistant-optional).

## Install the app

1. Download the latest `AstroTwo-….dmg` from the [Releases](https://github.com/guidogg13/AstroTwo/releases) page.
2. Open the `.dmg` and drag **AstroTwo** to *Applications*. Python and all the libraries AstroTwo needs are inside the app. You do not need to install anything else.
3. Start AstroTwo from *Applications*.

### First launch

The app is not yet signed with an Apple Developer ID or notarized, so macOS blocks the first launch. To allow it:

1. Try to open AstroTwo once and close the warning.
2. Open **System Settings → Privacy & Security**.
3. Next to the message about AstroTwo, click **Open Anyway** and confirm.

You only need to do this once for each version.

## Run from source (for developers)

Requires [uv](https://docs.astral.sh/uv/). uv installs Python 3.12 and the dependencies listed in `pyproject.toml`.

```bash
git clone https://github.com/guidogg13/AstroTwo.git
cd AstroTwo
uv run astrotwo
```

The tests run with:

```bash
uv run python -m pytest -q
```

The default test suite never uses the network. Tests that need real online services are marked `network` and run separately.

## Where AstroTwo keeps its files

- **Cache** of tiles, catalogues and service answers: `~/Library/Caches/AstroTwo/`. Its size limit is set in *Settings*.
- **Saved object profiles and tables received through SAMP:** `~/Library/Application Support/AstroTwo/`.
- **API keys for the AI assistant:** only in the **macOS Keychain**, never in files or logs.

## Uninstall

Drag AstroTwo from *Applications* to the Bin. To remove its data as well, delete `~/Library/Caches/AstroTwo/` and `~/Library/Application Support/AstroTwo/`. API keys can be deleted from the assistant settings (**Delete** next to the key), or with the *Keychain Access* app.
