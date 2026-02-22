require("dotenv").config();
const TelegramBot = require("node-telegram-bot-api");
const Groq = require("groq-sdk");
const fs = require("fs");

// ─────────────────────────────────────────────
// CONFIGURATION
// ─────────────────────────────────────────────
const TELEGRAM_TOKEN = process.env.TELEGRAM_TOKEN;
const GROQ_API_KEY   = process.env.GROQ_API_KEY;
const DEFAULT_LANG   = "hinglish";
const MEMORY_FILE    = "memory.json";
// ─────────────────────────────────────────────

const groq = new Groq({ apiKey: GROQ_API_KEY });
const bot  = new TelegramBot(TELEGRAM_TOKEN, { polling: true });

// ─────────────────────────────────────────────
// MEMORY STORAGE (Persistent JSON)
// ─────────────────────────────────────────────
function loadMemory() {
  if (!fs.existsSync(MEMORY_FILE)) {
    return {};
  }
  return JSON.parse(fs.readFileSync(MEMORY_FILE));
}

function saveMemory(memory) {
  fs.writeFileSync(MEMORY_FILE, JSON.stringify(memory, null, 2));
}

let memoryStore = loadMemory();

// Store each user's preferred language
const userLangMap = {};

console.log("✅ Memory-enabled Bot is running!");
console.log("📌 Type /language to switch language");
console.log("📌 Type /reset to clear memory");

// ─────────────────────────────────────────────
// STEP 1: Get Hindi Answer (with memory)
// ─────────────────────────────────────────────
async function getHindiAnswer(userMessage, history = []) {
  const response = await groq.chat.completions.create({
    model: "llama-3.3-70b-versatile",
    messages: [
      {
        role: "system",
        content: `You are a helpful assistant.
Always reply in simple Hindi (Devanagari script).
Keep reply short and conversational.`,
      },
      ...history,
      {
        role: "user",
        content: userMessage,
      },
    ],
  });

  return response.choices[0].message.content;
}

// ─────────────────────────────────────────────
// STEP 2: Translate Hindi to Pahari Dialects
// ─────────────────────────────────────────────
async function translateToPahari(hindiText, dialect) {

  const dialectInstructions = {
    pahari: `Translate Hindi text into General Himachali Pahari.
Use Devanagari. Sound like local Himachali speaking casually.`,

    kangri: `Translate Hindi text into Kangri dialect (Kangra region).
Use Devanagari. Casual local tone.`,

    mandyali: `Translate Hindi text into Mandyali dialect (Mandi region).
Use Devanagari. Friendly local tone.`,
  };

  const instruction = dialectInstructions[dialect] || dialectInstructions["pahari"];

  const response = await groq.chat.completions.create({
    model: "llama-3.3-70b-versatile",
    messages: [
      {
        role: "system",
        content: `You are an expert translator.
${instruction}
IMPORTANT:
- Only output translated text
- No explanation
- No English
- Keep friendly tone`,
      },
      {
        role: "user",
        content: hindiText,
      },
    ],
  });

  return response.choices[0].message.content;
}

// ─────────────────────────────────────────────
// MAIN AI FUNCTION (with memory support)
// ─────────────────────────────────────────────
async function askAI(userMessage, lang, history = []) {
  try {
    if (lang === "hinglish") {

      const response = await groq.chat.completions.create({
        model: "llama-3.3-70b-versatile",
        messages: [
          {
            role: "system",
            content: `You are a friendly assistant for people from Himachal Pradesh.
Always reply in simple Hinglish.
Short and conversational.`,
          },
          ...history,
          { role: "user", content: userMessage },
        ],
      });

      return response.choices[0].message.content;

    } else {

      const hindiAnswer = await getHindiAnswer(userMessage, history);
      const pahariAnswer = await translateToPahari(hindiAnswer, lang);
      return pahariAnswer;
    }

  } catch (error) {
    console.error("AI error:", error.message);
    return "माफ़ करिए, थोड़ी दिक्कत आ रही है। थोड़ी देर बाद फिर कोशिश करें 🙏";
  }
}

// ─────────────────────────────────────────────
// LANGUAGE DISPLAY NAME
// ─────────────────────────────────────────────
function getLangName(lang) {
  const names = {
    hinglish: "Hinglish 🇮🇳",
    pahari:   "General Pahari 🏔️",
    kangri:   "Kangri 🏔️",
    mandyali: "Mandyali 🏔️",
  };
  return names[lang] || "Hinglish";
}

// ─────────────────────────────────────────────
// COMMANDS
// ─────────────────────────────────────────────
bot.onText(/\/start/, (msg) => {
  const userId = msg.from.id;
  if (!userLangMap[userId]) userLangMap[userId] = DEFAULT_LANG;
  bot.sendMessage(msg.chat.id, "Han G Maraj! Aaun Tusa Ra AI assistant aa 🤖");
});

bot.onText(/\/language/, (msg) => {
  const text = `Choose Language:
/set_hinglish
/set_pahari
/set_kangri
/set_mandyali`;
  bot.sendMessage(msg.chat.id, text);
});

bot.onText(/\/set_hinglish/, (msg) => {
  userLangMap[msg.from.id] = "hinglish";
  bot.sendMessage(msg.chat.id, "Language set to Hinglish 🇮🇳");
});

bot.onText(/\/set_pahari/, (msg) => {
  userLangMap[msg.from.id] = "pahari";
  bot.sendMessage(msg.chat.id, "Language set to General Pahari 🏔️");
});

bot.onText(/\/set_kangri/, (msg) => {
  userLangMap[msg.from.id] = "kangri";
  bot.sendMessage(msg.chat.id, "Language set to Kangri 🏔️");
});

bot.onText(/\/set_mandyali/, (msg) => {
  userLangMap[msg.from.id] = "mandyali";
  bot.sendMessage(msg.chat.id, "Language set to Mandyali 🏔️");
});

bot.onText(/\/reset/, (msg) => {
  const userId = msg.from.id.toString();
  memoryStore[userId] = [];
  saveMemory(memoryStore);
  bot.sendMessage(msg.chat.id, "🧠 Memory reset ho gayi hai!");
});

// ─────────────────────────────────────────────
// MAIN MESSAGE HANDLER (with memory)
// ─────────────────────────────────────────────
bot.on("message", async (msg) => {
  if (!msg.text || msg.text.startsWith("/")) return;

  const chatId   = msg.chat.id;
  const userId   = msg.from.id.toString();
  const userText = msg.text;
  const lang     = userLangMap[userId] || DEFAULT_LANG;

  if (!memoryStore[userId]) {
    memoryStore[userId] = [];
  }

  const history = memoryStore[userId].slice(-10);

  bot.sendChatAction(chatId, "typing");

  const reply = await askAI(userText, lang, history);

  memoryStore[userId].push({ role: "user", content: userText });
  memoryStore[userId].push({ role: "assistant", content: reply });

  saveMemory(memoryStore);

  bot.sendMessage(chatId, reply);
});

// ─────────────────────────────────────────────
// ERROR HANDLING
// ─────────────────────────────────────────────
bot.on("polling_error", (error) => {
  console.error("Polling error:", error.message);
});