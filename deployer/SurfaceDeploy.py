import os
from datetime import datetime
import shutil
import random
import string 
import re

class SurfaceDeploy:
    def __init__(self, user_id, plugin_name):
        # datetime.now().strftime("%m-%d-%y") + "--" + 
        self.subdomain = str(user_id) + "-" + self.slugify(plugin_name) + "-" + self.random_string() + "-" + self.random_string()
        self.subdomain_dir = "./deps/" + self.subdomain
        self.app_url = self.subdomain + ""
        # copy sample directory 
        shutil.copytree("./sample_surface_deployment_dir", self.subdomain_dir)

    def upload_logo(self, logo):
        file_extension = logo.filename.split(".")[-1]
        filename = f"{self.subdomain_dir}/.well-known/logo.{file_extension}"

        # remove existing sample logo.png
        if os.path.exists(filename):
            os.remove(filename)

        with open(filename, "wb") as f:
            contents = logo.file.read()
            f.write(contents)


    def set_configs(self, item):
        replace_mapping_ai_plugin = {
            # "[name_for_model]": item["name_for_model"],
            "[name_for_human]": item["name_for_human"],
            "[app_url]": self.app_url,
            # "[description_for_model]": item["description_for_model"],
            # "[description_for_human]": item["description_for_human"],
            # "[app_url]": self.vdb_index_name,
            # "[contact_email]": item["contact_email"],
            # "[legal_info_url]": item["legal_info_url"],
        }

        self.replace_in_file(self.subdomain_dir + "/.well-known/" + "ai-plugin.json", replace_mapping_ai_plugin)
        print("===========================")
        replace_mapping_openapi = {
            "[app_url]": self.app_url,
            "[openapi_title]": item["name_for_human"],
            "[openapi_description]": item["name_for_human"],
        }
        self.replace_in_file(self.subdomain_dir + "/.well-known/" + "openapi.yaml", replace_mapping_openapi)


    def replace_in_file(self, file_path, replace_dict):
        """
        Open a file, search for specific strings, replace them with others, and save the updated file.
        """
        # Read the contents of the file
        with open(file_path, "r") as file:
            file_contents = file.read()

        # Replace the search strings with the replace strings
        for search_str, replace_str in replace_dict.items():
            print(search_str, file_contents.find(search_str), replace_str)
            file_contents = file_contents.replace(search_str, replace_str)

        # Write the updated contents back to the file
        with open(file_path, "w") as file:
            file.write(file_contents)


    def random_string(self, length=5, include_uppercase=False):
        if include_uppercase:
            return ''.join(random.choice(string.ascii_letters) for i in range(length))
        else:
            return ''.join(random.choice(string.ascii_lowercase) for i in range(length))


    def slugify(self, s):
        s = s.lower().strip()
        s = re.sub(r'[^\w\s-]', '', s)
        s = re.sub(r'[\s_-]+', '-', s)
        s = re.sub(r'^-+|-+$', '', s)
        return s