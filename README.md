# Nano 🍌 Renderer-er V2

AI-powered **viewport rendering tool for Rhino 8 (macOS/Windows)** using **Google Gemini 2.5 Flash Image**.
The script captures your active Rhino viewport and generates a wide range of renderings (studio-quality, photo-realistic, stylized, etc) directly inside the Rhino workspace for quick visual exploration.

There are two viewport capture options available:

* **Nano_Banana_Renderer-er_2025.py: Automated clay conversion of the viewport.**
* **Nano_Banana_Renderer-er_2025_direct capture.py: Direct viewport capture with no conversion.**


---

## ✨ Features

* **Dual Workflow**

  * **📸 Capture & Process Viewport** – Clean clay render from the active Rhino view.
  * **🪄 Generate / 🔄 Iterate** – Create and refine variations using prompts or mood boards.
* **AI Memory System** – Keeps your conversation history for continuous refinement.
* **Viewport Capture** – Removes gridlines, curves, and edges automatically.
* **Mood Board Support** – Add up to 4 style reference images.
* **Camera-Aware** – Automatically reads lens, field of view, and projection type.
* **Cost & Token Tracker** – Tracks session and lifetime Gemini API usage.
* **Persistent Settings** – Saves API key, output folder, and preferences.
* **Built-in Timer & Preview Viewer** – Track render time and view results easily.

---

## 🧰 Installation

**Please watch the installation video shared in the repository.**

1. **Install dependencies**

   * Open Rhino 8
   * Run ScriptEditor
   * Tools > Advanced > Open Python 3 Shell

   ```bash
   pip install google-genai
   ```

3. **Download the script**

   `Nano_Banana_Renderer-er_2025.py`
   **OR**
   `Nano_Banana_Renderer-er_2025_direct capture.py`

4. **Run the script in Rhino 8**

   * Drag and drop the file into the Rhino viewport or run it via Script Editor

---

## 🔑 Setup

1. Get your **Google Gemini API key** from
   👉 [https://aistudio.google.com](https://aistudio.google.com)
2. Enter it under the **Setup** tab inside the app.
3. Choose an output folder for generated images.

---

## 💡 How to Use

1. **Switch to a clean display mode** - You can import the Viewport Capture.ini to get you started.**
2. **Capture 📷** – Captures the current Rhino viewport as a clean clay render.
3. **Generate 🪄** – Type a short prompt to generate creative variations.
4. **Iterate 🔄** – Replace your current reference with the generated image and keep refining.
5. **Show Last Generated** – Opens a viewer for your latest render.

---

## 💵 Current Pricing (Gemini 2.5 Flash Image, Oct 2025)

* **$0.039 / image** (≈1290 tokens)
* Text input: $0.30 / 1M tokens
* Text output: $2.50 / 1M tokens

---

## ⚖️ Data & Privacy Disclaimer

Nano Banana Renderer-er uses the **Google Gemini API** to generate images and process prompts.
When you use your own Gemini API key:

* Your data is sent securely to Google’s servers as part of the generation request.
* **For unpaid/free-tier users** (Google Workspace, personal accounts):
  Google may log and store data for service improvement, safety, and abuse prevention.
* **For paid Google Cloud Gemini plans (Enterprise, API Pro, or Vertex AI):**
  Google does **not use your prompts or images for training** and data is processed under your organization’s privacy terms.
* You can review the full policy here:
  👉 [Google AI Studio & Gemini API Data Privacy](https://ai.google.dev/terms)

By using this script, you agree to these terms and understand that the author is **not responsible for data handling or storage by Google**.

---

## 🧑‍💻 Author

**Designed & Developed by**
[S. Dogan Sekercioglu](https://www.dogansekercioglu.com)
© 2025 | Not affiliated with McNeel or Google
