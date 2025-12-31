"""Fetch images from free sources for Spot the Difference puzzles."""

import os
import requests
from PIL import Image
from io import BytesIO
import random
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()


class ImageFetcher:
    """Fetch images from Picsum/Lorem Picsum for puzzle generation."""

    def __init__(self):
        # Lorem Picsum - reliable, no API key needed
        self.picsum_base = "https://picsum.photos"

        # Setup Gemini for smart suggestions
        api_key = os.getenv('GEMINI_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            self.gemini = genai.GenerativeModel('gemini-flash-latest')
        else:
            self.gemini = None

        # Fallback search terms if no Gemini
        self.default_searches = [
            "colorful room interior",
            "busy city street",
            "kitchen with objects",
            "garden with flowers",
            "office desk workspace",
            "living room furniture",
            "beach with umbrellas",
            "park with trees",
            "restaurant dining",
            "bedroom interior",
            "toy store shelves",
            "library books",
            "cafe coffee shop",
            "market fruit vegetables",
            "playground children"
        ]

    def get_search_terms(self, count=5, theme=None):
        """Get search terms from Gemini or use defaults."""
        if self.gemini and theme:
            try:
                prompt = f"""Give me {count} specific image search terms for "Spot the Difference" puzzles.
Theme: {theme}

Requirements:
- Images should have multiple objects/details
- Good for finding subtle differences
- Colorful and visually interesting

Return ONLY the search terms, one per line, no numbering or explanation."""

                response = self.gemini.generate_content(prompt)
                terms = [line.strip() for line in response.text.strip().split('\n') if line.strip()]
                return terms[:count]
            except Exception as e:
                print(f"Gemini error: {e}, using defaults")

        return random.sample(self.default_searches, min(count, len(self.default_searches)))

    def fetch_image(self, search_term=None, width=1920, height=1080, retries=3):
        """Fetch a random image from Lorem Picsum with retry logic."""
        import time

        for attempt in range(retries):
            # Lorem Picsum gives random high-quality images
            # Add random seed to get different images
            seed = random.randint(1, 10000)
            url = f"{self.picsum_base}/{width}/{height}?random={seed}"

            try:
                response = requests.get(url, timeout=15, allow_redirects=True)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    # Convert to RGB if needed
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    return img
                else:
                    print(f"Fetch attempt {attempt + 1} failed: {response.status_code}")
            except Exception as e:
                print(f"Fetch attempt {attempt + 1} error: {e}")

            # Wait before retry
            if attempt < retries - 1:
                time.sleep(1)

        print(f"Failed to fetch image after {retries} attempts")
        return None

    def fetch_multiple(self, count=5, theme=None, width=1920, height=1080):
        """Fetch multiple images for puzzle generation."""
        search_terms = self.get_search_terms(count, theme)
        images = []

        for term in search_terms:
            print(f"Fetching: {term}")
            img = self.fetch_image(term, width, height)
            if img:
                images.append({
                    'image': img,
                    'search_term': term
                })

        return images


# Test
if __name__ == "__main__":
    fetcher = ImageFetcher()

    # Test search terms
    terms = fetcher.get_search_terms(3, "cozy indoor scenes")
    print("Search terms:", terms)

    # Test image fetch
    img = fetcher.fetch_image("colorful living room")
    if img:
        print(f"Fetched image: {img.size}")
        img.save("test_fetch.jpg")
        print("Saved to test_fetch.jpg")
