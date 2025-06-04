import logging
from tqdm import tqdm
from typing import List, Dict, Optional, Any
import requests
from bs4 import BeautifulSoup
import csv
import time

# Configure logging at the module level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def scrape_ncss_data(max_pages: int = 5, output_csv_file: str = 'ncss_data.csv') -> None:
    """
    Scrapes data from ncss.cn based on pageIndex and saves it to a CSV file.

    Args:
        max_pages (int): The maximum number of pages to scrape.
        output_csv_file (str): The name of the CSV file to save data to.
    """
    base_url: str = "https://cy.ncss.cn/mtcontest/mingtilist"
    domain_url: str = "https://cy.ncss.cn"  # For constructing absolute URLs from relative paths

    # Headers extracted from your cURL command
    headers: Dict[str, str] = {
        'Accept': '*/*',
        'Accept-Language': 'en,en-US;q=0.9,zh-CN;q=0.8,zh;q=0.7,en-GB;q=0.6,zh-TW;q=0.5',
        'Connection': 'keep-alive',
        'Referer': 'https://cy.ncss.cn/mtcontest/list',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36 Edg/138.0.0.0',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"'
    }

    # Cookies extracted from your cURL command (ensure \u0021 is replaced with !)
    cookies_str = "CHSICC_CLIENTFLAGCYEN=e3544855a0304de573f9aefe74a74efa; CHSICC01=!nBCzFgzwQUdnRbrzYxYLahOzddj6Y/RWnAKLRcX+C7pPF2vDaeqkMztM0/Qmt90Q5nln0Hj3Np8R; _ga=GA1.1.2080840458.1747914959; XSRF-CCKTOKEN=0eca803f9595e9f5c4f615b90460b2a6; _ga_1ESVLDHDYL=GS2.1.s1749037369$o2$g1$t1749038251$j31$l0$h0; JSESSIONID=E81380FB86591785ECF8541E6B6BEC8C; CHSICC_CLIENTFLAGCY=721422c157a69713044fbaca55394600"
    cookies: Dict[str, str] = {cookie.split('=', 1)[0].strip(): cookie.split('=', 1)[1].strip() for cookie in cookies_str.split(';')}

    all_items_data: List[Dict[str, str]] = []
    logger.info(f"Starting to scrape data from {base_url}")

    for page_index in tqdm(range(1, max_pages + 1), desc="Scraping pages", unit="page"):
        # logger.info(f"Scraping page {page_index} of {max_pages}...") # Removed for tqdm
        try:
            params = {
                'pageIndex': page_index,
                'pageSize': 30,  # As per your cURL command
            'companyName': '',
            'name': '',
            'zbdm': '',
            'lbdm': ''
        }

            response: requests.Response = requests.get(base_url, headers=headers, cookies=cookies, params=params, timeout=20)
            response.raise_for_status()  # Will raise an HTTPError for bad responses (4xx or 5xx)

            # The response seems to be a list of <li> elements directly
            html_content: str = response.text
            soup: BeautifulSoup = BeautifulSoup(html_content, 'html.parser')

            list_items: List[Any] = soup.find_all('li')

            if not list_items and page_index > 1:  # If a page (not the first) returns no items, assume we're done
                logger.info(f"No items found on page {page_index}. Stopping.")
                break

            page_data_found = False
            for item_li in list_items:
                link_tag = item_li.find('a')
                if not link_tag:
                    continue

                href = link_tag.get('href')
                full_link = domain_url + href if href and href.startswith('/') else href

                title_div = item_li.find('div', class_='cymt-left')
                item_title = title_div.get('title') if title_div else ''

                company_div = item_li.find('div', class_='cymt-mtqy')
                item_company = company_div.get('title') if company_div else ''

                group_div = item_li.find('div', class_='cymt-mtzb')
                item_group = group_div.get('title') if group_div else ''

                category_div = item_li.find('div', class_='cymt-mtlb')
                item_category = category_div.get('title') if category_div else ''

                all_items_data.append({
                    'Link': full_link,
                    'Title': item_title,
                    'Company': item_company,
                    'Group': item_group,
                    'Category': item_category
                })
                page_data_found = True

            if not page_data_found and page_index > 0:  # Check if any data was extracted for this page
                logger.info(f"No parsable data found on page {page_index}, though HTTP request was successful.")

            # Be polite to the server
            time.sleep(1)  # Wait for 1 second between requests

        except requests.exceptions.Timeout:
            logger.warning(f"Request for page {page_index} timed out. Skipping.")
            continue
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching page {page_index}: {e}")
            # If a specific error like 403 (Forbidden) occurs, cookies might be an issue
            if e.response.status_code == 403:
                logger.error("Received 403 Forbidden. Cookies might be invalid or expired.")
            break  # Stop on HTTP errors
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching page {page_index}: {e}")
            break  # Stop on other request errors
        except Exception as e:
            logger.exception(f"An unexpected error occurred while processing page {page_index}:")
            continue  # Skip to next page or break, depending on desired robustness

    if not all_items_data:
        logger.info("No data was scraped. The CSV file will not be created.")
        return

    # Write data to CSV file
    csv_fieldnames: List[str] = ['Link', 'Title', 'Company', 'Group', 'Category']
    try:
        with open(output_csv_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_fieldnames)
            writer.writeheader()
            writer.writerows(all_items_data)
        logger.info(f"Data successfully scraped and saved to '{output_csv_file}'")
    except IOError:
        logger.error(f"I/O error writing to CSV file '{output_csv_file}'.")


# --- How to use ---
if __name__ == '__main__':
    # Set the number of pages you want to scrape.
    # For a "small batch" for debugging, you can start with 1 or 2.
    pages_to_scrape = 233  # Example: scrape the first 2 pages

    # You can change the output file name if needed
    csv_filename = 'mingti_data.csv'

    scrape_ncss_data(max_pages=pages_to_scrape, output_csv_file=csv_filename)