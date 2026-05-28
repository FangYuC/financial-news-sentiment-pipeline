import json

def load_stock_dict(json_file):
    """Load stock data from a JSON file."""
    try:
        with open(json_file, "r") as file:
            stock_dict = json.load(file)

        combined_dict = {}
        for key in stock_dict:
            combined_dict.update(stock_dict[key])

        return combined_dict

    except Exception as e:
        raise RuntimeError(f"Failed to load stock dict: {e}")
