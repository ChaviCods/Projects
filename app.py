import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify
from datetime import datetime

app = Flask(__name__)

base_url = 'http://vitibrasil.cnpuv.embrapa.br/index.php?'

endpoints = {
    'producao': 'opcao=opt_02',
    'processamento': 'opcao=opt_03',
    'comercializacao': 'opcao=opt_04',
    'importacao': 'opcao=opt_05',
    'exportacao': 'opcao=opt_06'
}

def scrape_page(url, endpoint):
    try:
        response = requests.get(url, timeout=10)  # Set a timeout of 10 seconds
        response.raise_for_status()  # Raise an HTTPError for bad responses
        soup = BeautifulSoup(response.content, 'html.parser')

        flattened_data = []
        current_category = None

        table = soup.find('table', class_='tb_base tb_dados')

        # Extract the year directly from URL
        current_year = int(url.split('ano=')[1].split('&')[0])

        header_cells = table.find('thead').find_all('th')
        for row in table.find('tbody').find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == len(header_cells):  # Data row
                row_data = {}
                for i, cell in enumerate(cells):
                    value = cell.text.strip().replace('.', '')  # Clean the value
                    try:
                        value = int(value) if value != '-' else None  # Convert to int or None
                    except ValueError:
                        pass  # Handle non-numeric values (if any)

                    header_text = header_cells[i].text.strip()
                    row_data[header_text] = value

                # Assign "Produto" to "item" if endpoint is "producao" or "comercializacao"
                if endpoint in ["producao", "comercializacao"] and "Produto" in row_data:
                    row_data["item"] = row_data.pop("Produto")

                # Assign unit based on the header
                if "Quantidade (L.)" in row_data:
                    row_data["unit"] = "L"
                elif "Quantidade (Kg)" in row_data:
                    row_data["unit"] = "Kg"

                if current_category:
                    row_data['category'] = current_category
                row_data["year"] = current_year

                # Skip if any value is None
                if not any(value is None for value in row_data.values()): 
                    flattened_data.append(row_data)

            elif len(cells) == 1 and 'tb_item' in row.td['class']:  # Category row
                current_category = cells[0].text.strip()
        if not flattened_data:  # If no data was extracted for the year, return None to filter it out later
            return None

        return flattened_data
    except requests.exceptions.RequestException as e:
        return f"Error fetching data from {url}: {e}"
    
    except Exception as e:  # Catch-all for other potential errors
        return f"An unexpected error occurred: {e}"

# API Endpoints (Modified to use URL for year iteration)
@app.route('/<endpoint>')
def get_data(endpoint):
    if endpoint not in endpoints:
        return jsonify({"error": "Invalid endpoint"}), 404

    all_years_data = []
    for year in range(1970, datetime.now().year + 1):  # Iterate up to the current year
        url = f"{base_url}{endpoints[endpoint]}&ano={year}"  
        year_data = scrape_page(url, endpoint)
        if isinstance(year_data, str):
            return jsonify({"error": year_data}), 500
        if year_data:  # This ensures only valid data is added
            all_years_data.extend(year_data)

    return jsonify(all_years_data)  # Return the flattened list directly

# Error Handling (404)
@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)