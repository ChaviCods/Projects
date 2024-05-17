# Importa as libraries necessárias (web scraping, framework, JSON responses, e data)
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify
from datetime import datetime
from flasgger import Swagger  # para a documentação da API

app = Flask(__name__)
swagger = Swagger(app)

# URL base do site a ser scraped
base_url = 'http://vitibrasil.cnpuv.embrapa.br/index.php?'

# Dicionário mapeando os nomes dos endpoints aos parametros do site para as respectivas paginas.
endpoints = {
    'producao': 'opcao=opt_02',
    'processamento': 'opcao=opt_03',
    'comercializacao': 'opcao=opt_04',
    'importacao': 'opcao=opt_05',
    'exportacao': 'opcao=opt_06'
}

# Função de scraping
def scrape_page(url, endpoint):
    try:
        response = requests.get(url, timeout=10)  # lida com timeout (max 10s)
        response.raise_for_status()  # lida com erros chamando a url
        soup = BeautifulSoup(response.content, 'html.parser')  # processa a pagina html.

        flattened_data = []
        current_category = None

        table = soup.find('table', class_='tb_base tb_dados')  # localiza a tabela que queremos

        # Extrai o ano da URL
        current_year = int(url.split('ano=')[1].split('&')[0])  

        header_cells = table.find('thead').find_all('th')
        for row in table.find('tbody').find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == len(header_cells):
                row_data = {}
                for i, cell in enumerate(cells):
                    value = cell.text.strip().replace('.', '')
                    try:
                        value = int(value) if value != '-' else None  # transforma "-" em None para logica de linhas vazias
                    except ValueError:
                        pass

                    header_text = header_cells[i].text.strip()
                    row_data[header_text] = value

                # Renomeando "Produto" para "item" para uniformizar
                if endpoint in ["producao", "comercializacao"] and "Produto" in row_data:
                    row_data["item"] = row_data.pop("Produto")

                # Determina a unidade baseado no header
                if "Quantidade (L.)" in row_data:
                    row_data["unit"] = "L"
                elif "Quantidade (Kg)" in row_data:
                    row_data["unit"] = "Kg"

                if current_category:
                    row_data['category'] = current_category
                row_data["year"] = current_year

                # Ignora linhas com valores vazios
                if not any(value is None for value in row_data.values()): 
                    flattened_data.append(row_data)

            elif len(cells) == 1 and 'tb_item' in row.td['class']:
                current_category = cells[0].text.strip()
        
        if not flattened_data:  # exclui anos vazios se houver
            return None

        return flattened_data
    except requests.exceptions.RequestException as e:  # lida com erros de rede
        return f"Error fetching data from {url}: {e}"

    except Exception as e:  # lida com erros não esperados.
        return f"An unexpected error occurred: {e}"


# API Endpoints (modificado pra usar a URL para iterar por todos os anos disponiveis
@app.route('/<endpoint>')
def get_data(endpoint):

# Swagger documentation
    """
    Get data for a specific vitiviniculture sector and all years.
    ---
    parameters:
      - name: endpoint
        in: path
        type: string
        enum: ['producao', 'processamento', 'comercializacao', 'importacao', 'exportacao']
        required: true
        description: url pra solicitar os dados por tipo.
    definitions:
      DataPoint:
        type: object
        properties:
          Quantidade (L.):
            type: integer
          Quantidade (Kg):
            type: integer
          Valor (US$):
            type: integer
          Países:
            type: string
          item:
            type: string
          unit:
            type: string
          year:
            type: integer
    responses:
      200:
        description: retorna a categoria selecionada (todos os anos)
        schema:
          type: array
          items:
            $ref: '#/definitions/DataPoint'
      404:
        description: Invalid endpoint.
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: Error fetching data.
        schema:
          type: object
          properties:
            error:
              type: string
    """

    if endpoint not in endpoints:
        return jsonify({"error": "Invalid endpoint"}), 404  # se a endpoint for invalida, retorna 404

    all_years_data = []
    for year in range(1970, datetime.now().year + 1):  # Faz a iteração em todos os anos até o ano corrente
        url = f"{base_url}{endpoints[endpoint]}&ano={year}"  # Prepara a URL com o ano em questão
        year_data = scrape_page(url, endpoint)  # executa o scrape
        if isinstance(year_data, str):
            return jsonify({"error": year_data}), 500  # Retorna 500 com o erro caso de algum problema com o ano solicitado
        if year_data:
            all_years_data.extend(year_data)  # Adiciona a lista

    return jsonify(all_years_data)  # Retorna os dados de todos os anos


@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404  # Retorna 404 se o endpoint não existe.


if __name__ == '__main__':
    app.run(debug=True)  # debug mode.
