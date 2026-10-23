&#x20;Luggage Price Scraper



A Python script that collects luggage cover product data from Amazon, Daraz and Samsonite, and saves it to CSV and Excel files.



\## What it does



\- Searches Amazon for a keyword and reads product name, brand, price and rating

\- Reads product details from a list of Daraz and Samsonite product links

\- Waits a random 5 to 20 seconds between requests to avoid overloading websites

\- Retries failed requests up to 3 times

\- Prints a summary table in the terminal

\- Saves the results to `luggage\_products.csv` and `luggage\_report.xlsx`



\## Tools used



\- Python

\- BeautifulSoup (HTML parsing)

\- curl\_cffi (web requests)

\- openpyxl (Excel output)

\- csv, json, re, logging (Python standard library)



\## How to run



1\. Install the libraries:



```

pip install beautifulsoup4 curl\_cffi openpyxl

```



2\. Run the script:



```

python scraper.py

```



3\. Open `luggage\_products.csv` or `luggage\_report.xlsx` to see the results.



\## Settings



Settings are at the top of `scraper.py`:



\- `AMAZON\_KEYWORD` and `AMAZON\_PAGES`: what to search for on Amazon, and how many pages

\- `DARAZ\_LINKS` and `SAMSONITE\_LINKS`: product links to read

\- `RUN\_AMAZON`, `RUN\_DARAZ`, `RUN\_SAMSONITE`: turn each website on or off



\## Output columns



date, site, item\_id, name, brand, price, currency, rating, stock, image\_url, product\_url



\## Known limitations



\- Daraz: product names are collected, but price and rating are not found yet (shown as N/A)

\- Amazon: requests may be blocked, in which case no Amazon data is returned

\- Websites change their layout often, so the script may need updates over time



\## Status



Learning project. Improvements in progress.

