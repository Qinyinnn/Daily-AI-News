# Daily-AI-News

<img width="1393" alt="Screenshot 2025-04-14 at 19 58 57" src="https://github.com/user-attachments/assets/287d30df-c799-400c-850f-6943077f1c9d" />

A Flask-based web application that aggregates and summarizes the latest AI news from top tech publications, featuring an elegant newspaper-style UI with Apple Intelligence-inspired design.

## Features

- **AI News Aggregation**: Fetches latest AI-related articles from:
  - CNN Tech
  - Ars Technica (currently experiencing issues)
- **Smart Summarization**: Uses DeepSeek API to generate concise summaries and explanation of complex AI news
- **Modern Newspaper UI**: Elegant typography with responsive design
- **API Endpoints**: JSON endpoints for integration with other applications

## Current Status

⚠️ **Known Issues**:
- **Ars Technica Crawler**: Currently experiencing reliability issues due to:
  - Frequent anti-bot measures by the website
  - Inconsistent HTML structure across pages
  - Potential IP blocking during heavy scraping
- **Working on implementing**:
  - Faster speed to fetch news from other websites
  - Optional proxy support

✅ **Stable Features**:
- CNN Tech scraping working reliably
- DeepSeek API integration fully functional
- Core UI/UX complete

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/daily-ai-news.git
   cd daily-ai-news
2. Set up a virtual environment:
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
3. Install dependencies:
   pip install -r requirements.txt
4. Create a .env file with your API key:
   DEEPSEEK_API_KEY=your_api_key_here

## Usage
1. Run the Flask application:
   python app.py
2. Access the web interface at:
   http://localhost:5001
3. API Endpoints:
   Get news: GET /api/news
   Explain article: POST /api/explain (requires JSON with "url")

## Configuration
Environment variables:
- DEEPSEEK_API_KEY: Required for AI explanations
- FLASK_ENV: Set to "development" for debug mode
- REQUEST_TIMEOUT: Timeout for web requests (default: 15s)

## Contributing:
I welcome contributions! Current priorities:
- Fix Ars Technica crawler reliability
- Add more news sources
- Improve error handling

Please open an issue to discuss before submitting major changes.
