import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime


# Helper utility - takes the old phylactery database, and converts it into a few json files so data can be migrated.
def split_json(db_json_filename):
	models = defaultdict(list)
	base_directory = Path()
	
	with open(db_json_filename, "r") as json_infile:
		json_data = json.load(json_infile)
		
	for entry in json_data:
		model_type = entry["model"]
		models[model_type].append(entry)
	
	for model_type in models.keys():
		with open(base_directory / "pretty_models" / "second" / f"{model_type}.json", "w") as json_outfile:
			json_outfile.write(f"// {datetime.today()} \n")
			json.dump(
				models[model_type],
				json_outfile,
				indent=2,
			)


if __name__ == "__main__":
	split_json("dbcopy20240906.json")
