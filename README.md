# Discord AI User - Kate

This project contains a selfbot style Discord user powered by OpenAI.  It uses
long and short‑term memory files to emulate a persistent character that chats on
Discord.  The main script (`main.py`) connects to Discord using the token from a
`.env` file and responds to messages using OpenAI's chat models.

## Setup
1. **Python** – Python 3.10 or newer is recommended.
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment variables** – Create a `.env` file with your Discord user token
   and OpenAI API key:
   ```bash
   DISCORD_USER_TOKEN=your_token_here
   OPENAI_API_KEY=your_openai_key
   ```
4. **Run** – start the bot with:
   ```bash
   python main.py
   ```

All runtime data such as chat logs and relationship information is stored in the
`memory/` directory.

## Repository layout
- `main.py` – entry point for the bot
- `kate/` – package containing modules for memory, personality and behaviour
- `config/` – configuration files

Temporary files (`memory`, `logs` and Python bytecode) are ignored via
`.gitignore`.
