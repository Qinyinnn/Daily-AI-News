import markdown # for bond fonts
from markupsafe import Markup
from flask import Flask, render_template, request, jsonify, session # session: store user data temporarily; render_template: show HTML pages
import os # work with files/folders
import requests # make web requests
import json
import time # for time.sleep(1) to add a delay between requests to avoid overwhelming the server
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv # Load environment variables
import random

# Create Flask APP
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for session usage
load_dotenv()

"""
Explain text using DeepSeek API
Args: text (str) - News content to explain
Returns: str - processed news
"""
def explain_with_deepseek(text):
    print(f"Using API key: {os.getenv('DEEPSEEK_API_KEY')}")

    headers = {
        "Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY')}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "You are a professional AI news editor. "
                           "Extract and summarize the key insights from this news article about artificial intelligence. "
                           "Focus on technological advancements, business impacts, ethical considerations, and regulatory developments. "
                           "Keep it easy to understand and under 250 words."
            },
            {
                "role": "user",
                "content": text
            }
        ]
    }
    
    try:
        response = requests.post( # send request to DeepSeek API
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60 # a time limit for an operation to complete
        )
        response.raise_for_status()
        
        result = response.json()
        
        print(f"API Response Status: {response.status_code}")
        print(f"API Response: {result}")
        
        if 'choices' in result and len(result['choices']) > 0:
            if 'message' in result['choices'][0] and 'content' in result['choices'][0]['message']:
                # Convert Markdown to HTML
                markdown_text = result['choices'][0]['message']['content']
                html_content = markdown.markdown(markdown_text)
                return Markup(html_content)  # if successful, return the AI's summary
            else:
                return f"Unexpected response structure: 'message' or 'content' key missing in choices"
        else:
            return f"API returned unexpected format: {result}"

    except requests.exceptions.HTTPError as http_err:
        return f"HTTP error occurred: {http_err} - Check your API key"
    except requests.exceptions.ConnectionError:
        return "Connection error: Could not connect to the DeepSeek API"
    except requests.exceptions.Timeout:
        return "Timeout error: The request to DeepSeek API timed out"
    except requests.exceptions.RequestException as req_err:
        return f"Request error: {req_err}"
    except KeyError as key_err:
        return f"Response parsing error: Key '{key_err}' not found in API response"
    except Exception as e:
        return f"Explanation by DeepSeek failed: {str(e)}"


def extract_news_from_url(url):
    headers = {
        #pretending to be a real browser, avoid being blocked
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # raise an exception if the HTTP request returned an unsuccessful status
        soup = BeautifulSoup(response.text, "html.parser")

        # Site-specific handling
        if "arstechnica.com" in url:
            # Try Ars Technica specific content first
            content_container = soup.select_one("div.article-content, .article-guts")
            if content_container:
                paragraphs = content_container.select("p")
                if paragraphs:
                    return "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        # Check for structured data first (JSON-LD)
        ld_json = soup.find("script", {"type": "application/ld+json"})
        if ld_json:
            try:
                data = json.loads(ld_json.string)
                if "articleBody" in data:
                    return data["articleBody"]
            except (json.JSONDecodeError, AttributeError) as e:
                print(f"Could not extract JSON-LD data: {e}")

        # If no structured JOSN data was found, try to find article content using various selectors
        content = ""
        
        selectors = [
            # CNN article structure selectors in priority order
            # Article content with rail layout
            "div.article__content",
            "div.zn-body__paragraph",
            "div.article-body__content",
            # Standard article containers
            "article[data-page-type='article'] div.l-container",
            "article[data-page-type='article'] div.pg-rail-tall__body",
            # Fallback to any container with article paragraphs
            "div.body-text",
            "div.article__main"

            # Add Ars Technica specific selectors
            "div.article-content",
            "div.post-content",
            "article.article-content",
            "div.story-content",
            ".article-guts",
            "div[itemprop='articleBody']"
        ]
        
        for selector in selectors:
            container = soup.select_one(selector)
            if container:
                paragraphs = container.select("p")
                if paragraphs:
                    # Joins their cleaned-up text into one big string and stores it in content.
                    content = "\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                    if content:
                        break
        
        # If still no content, try a more generic approach
        if not content:
            # Look for any paragraphs that are likely part of the article
            all_paragraphs = soup.select("p")
            # Filters out short ones (less than 40 characters) or ones inside a <header>, 
            # assuming those aren’t part of the article.
            article_paragraphs = [p.get_text(strip=True) for p in all_paragraphs 
                                 if len(p.get_text(strip=True)) > 40 and not p.find_parent("header")]
            if article_paragraphs:
                content = "\n".join(article_paragraphs)

        return content # returns the extracted article content

    except requests.exceptions.RequestException as e:
        print(f"Error extracting article from {url}: {e}")
        return ""


"""
Check if an article is AI-related by looking for keywords in its title and content
"""
def is_ai_related(title, content):
    # Reduced and more focused list of AI-related keywords
    ai_keywords = [
        "artificial intelligence", "machine learning", "deep learning", 
        "chatgpt", "openai", "anthropic", "claude", "gemini", 
        "large language model", "neural network", "deepseek"
    ]
    
    # Combine title and content for searching, turning content to lower case to avoid case-sensitivity
    text = (title + " " + content).lower()
    
    # Check if any keyword is in the text
    for keyword in ai_keywords:
        if keyword in text:
            return True
            
    return False


"""
Fetch news specifically from CNN Tech page
"""
def fetch_tech_news_from_cnn():
    tech_url = "https://edition.cnn.com/business/tech"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        print(f"Fetching news from CNN Tech page: {tech_url}")
        response = requests.get(tech_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # The CNN page has class "layout layout-no-rail business"
        articles = []
        
        # Look for main zones where articles might be
        content_zones = soup.select("div.container__field-links, div.container_lead-plus-headlines__item, div.container__item, div.zone__items")
        
        for zone in content_zones:
            # Find articles within each zone
            article_elements = zone.select("div.card, div.container__item, li.container__item, div.container_lead-plus-headlines__item")
            
            for article in article_elements:
                # Extract title
                title_element = article.select_one("span.container__headline-text, h3.container__headline-text, div.container__headline a, h3.cd__headline")
                if not title_element:
                    title_element = article.select_one("a[data]")  # Another common pattern
                
                if title_element:
                    title = title_element.get_text(strip=True)
                    
                    # Extract URL:
                    # This code is trying to reliably get a link to an article — sometimes the title itself is the link, 
                    # sometimes it's inside the title or surrounding elements. This handles both cases.
                    link_element = None
                    if title_element.name == "a": # <a> usually represents a hyperlink
                        link_element = title_element
                    else:
                        link_element = article.select_one("a")
                    
                    if link_element and link_element.has_attr("href"):
                        url = link_element["href"]
                        
                        # Format URL correctly 
                        if url.startswith("//"):
                            url = "https:" + url
                        elif url.startswith("/"):
                            url = "https://edition.cnn.com" + url
                        elif not url.startswith(("http://", "https://")):
                            url = "https://edition.cnn.com/" + url
                            
                        # Add to our articles list
                        if title and url:
                            if url not in [a.get("url") for a in articles]:
                                articles.append({"title": title, "url": url})
                    
                time.sleep(1) # wait 1 second per requests to avoid overwhelming the server
        
        # If we couldn't find articles with the specific selectors, try a more general approach
        if not articles:
            # Look for all headline-like elements
            headlines = soup.select("h3 a, .headline a, .headline-text, .container__headline-text")
            
            for headline in headlines:
                title = headline.get_text(strip=True)
                
                # Get URL
                url = None
                if headline.name == "a" and headline.has_attr("href"):
                    url = headline["href"]
                elif headline.parent and headline.parent.name == "a" and headline.parent.has_attr("href"):
                    url = headline.parent["href"]
                
                if title and url:
                    # Format URL
                    if url.startswith("//"):
                        url = "https:" + url
                    elif url.startswith("/"):
                        url = "https://edition.cnn.com" + url
                    elif not url.startswith(("http://", "https://")):
                        url = "https://edition.cnn.com/" + url
                        
                    # Add to articles list, to display on the webpage
                    if url not in [a.get("url") for a in articles]:
                        articles.append({"title": title, "url": url})
        
        print(f"Found {len(articles)} articles on CNN Tech page")
        return articles
        
    except Exception as e:
        print(f"Error fetching CNN Tech news: {e}")
        return []



def fetch_news_from_arstechnica():
    tech_url = "https://arstechnica.com/"
    
    headers = {
    "User-Agent": random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
    ]),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        print(f"Fetching news from Ars Technica: {tech_url}")
        response = requests.get(tech_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        articles = []
        
        # Based on the provided HTML, we need to look for elements with specific classes
        # Debug print to help identify structure
        print("Searching for articles...")
        
        # Looking for all article headlines using the class structure from the sample
        headlines = soup.select("h1.font-serif.text-3xl, h2.font-serif.text-xl")
        
        print(f"Found {len(headlines)} potential headlines")
        
        for headline in headlines:
            try:
                # Find the closest parent article or div that contains the full article info
                article_container = headline.find_parent("article") or headline.find_parent("div", class_="article")
                
                if article_container:
                    # Extract title
                    title = headline.get_text(strip=True)
                    
                    # Find URL - look for the closest anchor tag
                    link_element = headline.find_parent("a") or article_container.find("a", href=True)
                    
                    if link_element and link_element.has_attr("href"):
                        url = link_element["href"]
                        
                        # Format URL correctly
                        if url.startswith("//"):
                            url = "https:" + url
                        elif url.startswith("/"):
                            url = "https://arstechnica.com" + url
                        elif not url.startswith(("http://", "https://")):
                            url = "https://arstechnica.com/" + url
                        
                        # Extract author if available
                        author_element = article_container.select_one("a.text-orange-400")
                        author = author_element.get_text(strip=True) if author_element else None
                        
                        # Extract date if available
                        time_element = article_container.select_one("time")
                        published_date = time_element["datetime"] if time_element and time_element.has_attr("datetime") else None
                        
                        # Create article data dictionary
                        article_data = {
                            "title": title,
                            "url": url
                        }
                        
                        if author:
                            article_data["author"] = author
                        if published_date:
                            article_data["published_date"] = published_date
                        
                        # Add to articles list if not already present
                        if url not in [a.get("url") for a in articles]:
                            articles.append(article_data)
                            print(f"Added article: {title}")
            
            except Exception as e:
                print(f"Error processing headline: {e}")
                continue
        
        # If still no articles found, try alternative selectors
        if not articles:
            print("No articles found with primary selectors, trying alternative approach...")
            
            # Try finding articles using different class combinations
            alt_headlines = soup.select("div.dusk h1, div.dusk h2, h1.text-3xl, h2.text-xl")
            
            for headline in alt_headlines:
                title = headline.get_text(strip=True)
                link_element = headline.find_parent("a") or headline.find("a")
                
                if title and link_element and link_element.has_attr("href"):
                    url = link_element["href"]
                    
                    # Format URL
                    if url.startswith("//"):
                        url = "https:" + url
                    elif url.startswith("/"):
                        url = "https://arstechnica.com" + url
                    elif not url.startswith(("http://", "https://")):
                        url = "https://arstechnica.com/" + url
                    
                    if url not in [a.get("url") for a in articles]:
                        articles.append({"title": title, "url": url})
                        print(f"Added article (alternative method): {title}")
        
        print(f"Found {len(articles)} articles on Ars Technica")
        return articles
        
    except Exception as e:
        print(f"Error fetching Ars Technica news: {e}")
        return []
    


def fetch_ai_news():
    ai_articles = {
        "CNN Tech": [],
        "Ars Technica": []
    }
    
    # CNN Tech
    print("Fetching CNN Tech news...")
    cnn_articles = fetch_tech_news_from_cnn()
    print(f"Found {len(cnn_articles)} CNN articles before AI filtering")
    for article in cnn_articles:
        try:
            content_preview = extract_news_from_url(article["url"])
            if is_ai_related(article["title"], content_preview):
                article["preview"] = content_preview[:200] + "..." if content_preview else ""
                ai_articles["CNN Tech"].append(article)
        except Exception as e:
            print(f"Error processing CNN article: {e}")
    print(f"Found {len(ai_articles['CNN Tech'])} AI-related CNN articles")

    # Ars Technica
    print("\nFetching Ars Technica news...")
    arstechnica_articles = fetch_news_from_arstechnica()
    print(f"Found {len(arstechnica_articles)} Ars Technica articles before AI filtering")
    for article in arstechnica_articles:
        try:
            content_preview = extract_news_from_url(article["url"])
            if is_ai_related(article["title"], content_preview):
                article["preview"] = content_preview[:200] + "..." if content_preview else ""
                ai_articles["Ars Technica"].append(article)
        except Exception as e:
            print(f"Error processing Ars Technica article: {e}")
    print(f"Found {len(ai_articles['Ars Technica'])} AI-related Ars Technica articles")

    print("\n--- News fetch summary ---")
    for source, articles in ai_articles.items():
        print(f"{source}: {len(articles)} AI-related articles")
    
    return ai_articles


@app.route('/', methods=['GET', 'POST']) # allows both GET and POST HTTP methods
# This function interacts with human users
def home():
    # Initialize news dictionary with empty lists for each source
    ai_news = {
        "CNN Tech": [],
        "Ars Technica": []
    }
    explanation = ""
    generated_file = ""
    current_date = datetime.now().strftime("%B %d, %Y")  # Newspaper-style date format
    
    # If the user clicks a button on the page (like "Get the newest updates")
    # the code will fetch fresh AI news from the Internet and replace the old news with the new one
    if request.method == 'POST':
        action = request.form.get('action')
        
        # if the user fetches news
        if action == 'fetch_news':
            ai_news = fetch_ai_news()
            # Store fetched news in session so it can be reused
            session['ai_news'] = ai_news 
            return render_template('index.html', 
                                ai_news=ai_news,
                                current_date=current_date,
                                success="AI news articles fetched successfully!")
        
        # If the user clicks "Explain with AI"
        # (there is a button in the frontend page which has the name 'action' and value 'process_article'
        elif action == 'process_article':
            # Retrieve the article's URL and title from the form
            url = request.form.get('url')
            title = request.form.get('title')
            
            # Use stored news articles instead of fetching again
            if 'ai_news' in session:
                ai_news = session['ai_news']
            else:
                # Fall back if the session is empty
                return render_template(
                    'index.html',
                    ai_news=ai_news,  # Using initialized empty dictionary
                    current_date=current_date,
                    error="No AI news found. Click 'Refresh AI News' to fetch the latest articles.",
                )
                
            # Process the selected article
            try:
                news_text = extract_news_from_url(url)
                if news_text:
                    print(f"Extracted article content length: {len(news_text)} characters")
                    explanation = explain_with_deepseek(news_text)

                    print(f"Generated explanation: {explanation[:100]}...")
                    generated_file = generate_daily_report(explanation)
                    return render_template('index.html',
                                      ai_news=ai_news,  # Use stored news
                                      explanation=explanation,
                                      generated_file=generated_file,
                                      selected_title=title,
                                      current_date=current_date,
                                      success=f"News processed and saved to {generated_file}")
                else:
                    return render_template('index.html',
                                      ai_news=ai_news,  # Use stored news
                                      current_date=current_date,
                                      error="Could not extract content from the URL")
            except Exception as e:
                print(f"Error processing article: {str(e)}")
                return render_template('index.html',
                                   ai_news=ai_news,  # Use stored news
                                   current_date=current_date,
                                   error=str(e))
    
    # Handle GET requests: triggered by page loads (e.g. initial page loads)
    else:
        if 'ai_news' in session and session['ai_news']:
            ai_news = session['ai_news']
            print("Using cached news articles from session")
        else:
            try:
                print("Session empty, fetching fresh news articles")
                ai_news = fetch_ai_news()
                session['ai_news'] = ai_news
            except Exception as e:
                print(f"Error fetching initial news: {e}")
    
    # Add debugging information
    print("ai_news structure:", type(ai_news))
    for source, articles in ai_news.items():
        print(f"{source}: {len(articles)} articles")
    
    return render_template('index.html', 
                         ai_news=ai_news, 
                         explanation=explanation, 
                         generated_file=generated_file,
                         current_date=current_date)



@app.route('/api/news', methods=['GET'])
def api_news():
    # This function handles API requests for getting AI news (data only, no webpage)
    # It returns the news as JSON so it can be used by JavaScript or mobile apps.
    try:
        # Use cached news if available
        if 'ai_news' in session and session['ai_news']:
            ai_news = session['ai_news']
        else:
            ai_news = fetch_ai_news()
            session['ai_news'] = ai_news
        return jsonify({"status": "success", "news": ai_news})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/api/explain', methods=['POST'])

def api_explain():
    # This function handles API requests to explain an article.
    # It expects a JSON request with a "url" field.
    # It extracts the article content from the URL, generates an explanation,
    # and returns the explanation as JSON for the frontend or external apps to use.
    data = request.json
    url = data.get('url')
    
    if not url:
        return jsonify({"status": "error", "message": "URL is required"})
    
    try:
        news_text = extract_news_from_url(url)
        explanation = explain_with_deepseek(news_text)
        return jsonify({
            "status": "success", 
            "explanation": explanation
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# Run the app
if __name__ == '__main__':
     # debug=True can help auto-reloads on Code Change & detailed error page & verbose logging
     # Reminder: Use Debug Mode for Development Only, bc it’s a big security risk because:
     # Anyone can see errors and potentially run code in your app if they get to the debugger.
    app.run(host='0.0.0.0', port=5001, debug=True) 