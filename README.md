# Clinical Recall Assistant

A desktop study tool for paramedics that quizzes you on clinical knowledge using active recall, with AI-powered feedback grounded in source material. Built for the ACT Ambulance Service (ACTAS) clinical management guidelines and personal study documents.

---

## Download and Install

Pre-built installers are available from [GitHub Releases](https://github.com/opurtell/studyBotcode/releases).

### 1. Choose the right download

| Your machine | Download file |
|--------------|---------------|
| **Mac with Apple Silicon** (M1, M2, M3, M4 -- any Mac from late 2020 onwards) | `Clinical Recall Assistant-<version>-arm64.dmg` |
| **Mac with Intel** (any Mac before late 2020) | `Clinical Recall Assistant-<version>-x64.dmg` |
| **Windows PC** (Intel or AMD, 64-bit) | `Clinical Recall Assistant-<version>-Setup.exe` |

**Not sure which Mac you have?** Click the Apple menu () > **About This Mac**. If it says "Chip: Apple M1/M2/M3/M4", download the **arm64** version. If it says "Processor: Intel", download the **x64** version.

### 2. Install

**macOS:** Open the `.dmg` file and drag **Clinical Recall Assistant** into your Applications folder. On first launch, macOS may warn about an unidentified developer -- right-click the app and choose **Open** to bypass this.

**Windows:** Run the `.exe` installer and follow the prompts. Windows Defender SmartScreen may show a warning -- click **More info** > **Run anyway**.

### 3. Get an API key

The app needs an API key from an AI provider to generate quiz questions and evaluate your answers. You only need one provider. **Google Gemini is recommended** because it has a free tier.

#### Google Gemini (free tier available)

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click **Create API Key** -- select or create a Google Cloud project when prompted
4. Copy the key
5. Open the app, go to **Curator Settings**, paste the key into the Google field, and set Google as your active provider

#### Anthropic (Claude)

1. Go to [console.anthropic.com](https://console.anthropic.com/)
2. Create an account and add a payment method (pay-as-you-go, no minimum)
3. Go to **API Keys** and create a new key
4. Paste it into the Anthropic field in **Curator Settings**

#### Z.ai (Zhipu)

1. Go to [open.bigmodel.cn](https://open.bigmodel.cn/)
2. Register and go to API Keys
3. Create a key and paste it into the Z.ai field in **Curator Settings**

### 4. Start studying

Once your API key is set, you're ready to go. The app comes pre-loaded with ACTAS Clinical Management Guidelines. Start a quiz from the dashboard -- you can quiz across all categories or target specific topics.

---

## Developer Guide

Everything below is for contributors and developers who want to run from source or build the app themselves.

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Node.js** | 18+ | LTS recommended |
| **Python** | 3.10+ | Used by the backend; standalone Python is bundled for release builds |
| **npm** | 9+ | Comes with Node.js |
| **Git** | Any | To clone the repo |

### Quick Start (Development)

```bash
# 1. Clone the repo
git clone https://github.com/opurtell/studyBotcode.git
cd studyBotcode

# 2. Install Node dependencies
npm install

# 3. Install Python dependencies
pip install -e ".[dev]"

# 4. Create your local settings file
cp config/settings.example.json config/settings.json

# 5. (Optional) Create a .env for model overrides
cp .env.example .env

# 6. Start the Python backend
python3 src/python/main.py          # Runs on http://127.0.0.1:7777

# 7. In a separate terminal, start the Electron + Vite dev server
npm run dev                          # Vite on :5173, Electron connects automatically
```

### Configuring API keys (development)

In development, API keys live in `config/settings.json` (gitignored). Copy the example and add your key:

```bash
cp config/settings.example.json config/settings.json
```

Example using Google Gemini:

```json
{
  "providers": {
    "google": { "api_key": "YOUR_KEY_HERE", "default_model": "gemini-3.1-flash-lite-preview" }
  },
  "active_provider": "google",
  "quiz_model": "gemini-3.1-flash-lite-preview",
  "clean_model": "gemini-2.5-pro"
}
```

You can also use Anthropic or Z.ai -- just set the relevant `api_key` and `active_provider` fields. All three providers can be configured simultaneously and switched in the app's Settings screen.

### Model tiers

Each provider offers three tiers. Use fast models for quizzes (latency-sensitive) and strong models for OCR cleaning (accuracy matters).

| Tier | Anthropic | Google | Z.ai |
|------|-----------|--------|------|
| Low (fast) | `claude-haiku-4-5-20251001` | `gemini-3.1-flash-lite-preview` | `glm-4.7-flash` |
| Medium | `claude-sonnet-4.6` | `gemini-3-flash-preview` | `glm-4.7` |
| High (strong) | `claude-opus-4.6` | `gemini-2.5-pro` | `glm-5` |

---

### Building for Distribution

The app bundles a standalone Python 3.12 runtime so end users don't need Python installed. Builds are architecture-specific and must be built on the target platform (no cross-compilation).

#### Build commands

| Command | Platform | Output |
|---------|----------|--------|
| `npm run build:mac-arm64` | macOS (Apple Silicon) | `.dmg` in `release/` |
| `npm run build:mac-x64` | macOS (Intel) | `.dmg` in `release/` |
| `npm run build:win-x64` | Windows (64-bit) | `.exe` installer in `release/` |

Each build command:
1. Downloads a standalone Python 3.12 runtime for the target architecture
2. Installs all Python dependencies into the bundle
3. Pre-builds the ChromaDB vector index from bundled CMG data
4. Builds the Vite/React frontend
5. Packages everything with electron-builder

#### Architecture reference

| Architecture | Build flag | Machines |
|--------------|------------|----------|
| **arm64** | `--arm64` | All Apple Silicon Macs -- M1, M2, M3, M4 and their Pro/Max/Ultra variants. Every MacBook Air, MacBook Pro, Mac Mini, Mac Studio, Mac Pro, and iMac from late 2020 to present. |
| **x64** | `--x64` | Intel-based Macs (pre-late 2020): any MacBook Pro/Air, iMac, Mac Mini, or Mac Pro with an Intel Core processor. Also all standard Windows PCs and laptops with 64-bit Intel or AMD processors. |

#### CI/CD

Pushing a tag matching `v*` (e.g. `v0.2.0`) triggers the [release workflow](.github/workflows/release-build.yml), which builds all three targets (mac-arm64, mac-x64, win-x64) on GitHub Actions runners and creates a draft GitHub Release with the installers attached.

#### Personal builds

If you have your own study documents and a pre-built ChromaDB index, set the `PERSONAL_BUILD` flag to skip the CMG re-indexing step:

```bash
PERSONAL_BUILD=1 npm run build:mac-arm64
```

This expects a pre-populated `build/resources/data/chroma_db/` directory.

---

### Running Tests

```bash
# Frontend tests (vitest)
npm test

# Python backend tests (pytest)
pytest
```

---

### Project Structure

```
studyBotcode/
  src/
    electron/       Electron main process + preload
    python/         FastAPI backend (quiz, pipeline, search, settings)
    renderer/       React frontend (TypeScript + Tailwind)
  config/           Settings (settings.json is gitignored)
  data/             Processed data (CMGs, vector store)
  docs/             Source study documents
  scripts/          Build and packaging scripts
  tests/            Test suites (vitest + pytest)
  stitchDesign/     UI design prototypes and design system spec
```

---

### Troubleshooting

**Backend won't start:** Make sure you've installed Python dependencies (`pip install -e .`) and that port 7777 is free.

**No quiz questions generated:** Ensure you have at least one API key configured in `config/settings.json` and that the `active_provider` matches a provider with a valid key.

**`settings.json` missing:** Run `cp config/settings.example.json config/settings.json`. The backend falls back to the example file for basic startup, but you need the copy for local configuration.

**Build fails downloading Python:** The build scripts download a standalone Python from GitHub. Check your internet connection and that the URL in `scripts/package-backend.sh` is accessible.

**macOS "damaged" or "unidentified developer" warning:** Right-click the app > Open, or run `xattr -cr /Applications/Clinical\ Recall\ Assistant.app` in Terminal.

---

## Licence

This project is for personal educational use. The ACTAS Clinical Management Guidelines are the property of the ACT Ambulance Service.
