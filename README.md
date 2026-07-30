# 🚗 AutoAI – AI Car Recommendation Bot

An AI-powered car recommendation platform that helps users find the most suitable car based on their budget, fuel preference, transmission, family size, and priorities using Large Language Models (LLMs).

---

## 📌 Features

- 🤖 AI-powered natural language understanding
- 🚗 Personalized car recommendations
- 💰 Budget-based filtering
- ⛽ Fuel type recommendations (Petrol/Diesel/CNG/Electric)
- ⚙️ Manual & Automatic transmission support
- 👨‍👩‍👧 Family-size based recommendations
- 🧠 LLM-powered preference extraction
- 📊 PostgreSQL car database
- ⚡ FastAPI backend
- 💬 AI-generated explanation for every recommendation

---

## 🛠️ Tech Stack

### Backend
- Python
- FastAPI
- SQLAlchemy
- PostgreSQL

### AI
- OpenAI API
- Prompt Engineering
- Large Language Models (LLMs)

### Database
- PostgreSQL

### Tools
- Git
- GitHub
- VS Code

---

## 📂 Project Structure

```
AutoAI/
│
├── backend/
│   ├── app/
│   │   ├── models/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── schemas/
│   │   ├── database.py
│   │   └── main.py
│   │
│   ├── .env
│   └── requirements.txt
│
├── frontend/
│
├── data/
│
└── README.md
```

---

## 🚀 Installation

### Clone the repository

```bash
git clone https://github.com/sankalp1207/Auto-AI-car-recommendation-bot.git
```

### Go to the project directory

```bash
cd Auto-AI-car-recommendation-bot
```

### Create a virtual environment

```bash
python -m venv venv
```

### Activate it

Windows

```bash
venv\Scripts\activate
```

Linux / macOS

```bash
source venv/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment Variables

Create a `.env` file inside the backend directory.

```env
DATABASE_URL=your_database_url
OPENAI_API_KEY=your_api_key
SECRET_KEY=your_secret_key
```

### Start the backend

```bash
uvicorn app.main:app --reload
```

Open

```
http://127.0.0.1:8000/docs
```

---

## 🎯 Future Improvements

- User Authentication
- Car Comparison
- Wishlist
- Voice-based Recommendation
- Image-based Search
- Dealer Integration
- Price Prediction
- RAG-based Knowledge System

---

## 📸 Screenshots

Add screenshots here.

Example:

```
screenshots/home.png
screenshots/chat.png
screenshots/recommendation.png
```

---

## 👨‍💻 Author

**Sankalp Arora**

GitHub:
https://github.com/sankalp1207

LinkedIn:
https://www.linkedin.com/in/sankalp-arora-024a09332/

LeetCode:
https://leetcode.com/u/JuPeUB3Gj8/

---

## ⭐ If you found this project useful, consider giving it a star!
