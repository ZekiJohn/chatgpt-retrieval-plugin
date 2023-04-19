import os
from datetime import datetime
import shutil
import random
import string 
import re
import jwt


class SurfaceDeploy:
    def __init__(self, user_id, plugin_name, user_plan):
        # self.app_url = "https://personalized-retrieval-plugin.up.mygptplugin.com" # I can use this domain unless it is I submit and approved by OpenAI, why? bze using the same domain for unverified plugin will only allow upto 15 users
        
        self.subdomain = str(user_id) + "-" + self.slugify(plugin_name) + "-" + self.random_string() + "-" + self.random_string()
        self.subdomain_dir = "./deps/" + self.subdomain
        self.app_url = "https://" + self.subdomain + ".up.mygptplugin.com"
        
        if user_plan != "free" and user_plan != "hobby":
            # copy sample directory
            self.app_url = "https://personalize.mygptplugin.com"
            shutil.copytree("./sample_surface_deployment_dir", self.subdomain_dir)

        self.plugin_id = self.random_string()

    def generate_token(self, user_id, user_plan):
        secret = "3efdd8b59a11a31d912c6c4c1657607dfc994b1c92eaf9a021551774eb24bc00"
        return jwt.encode({
            "user": user_id, 
            "plan": user_plan, 
            "plugin": self.plugin_id,
            "subdomain": self.subdomain,
        }, secret, algorithm="HS256")


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
            "[name_for_model]": item["name_for_model"],
            "[name_for_human]": item["name_for_human"],
            "[app_url]": self.app_url,
            "[description_for_model]": item["description_for_model"],
            "[description_for_human]": item["description_for_human"],
            "[app_url]": self.app_url,
            "[contact_email]": item["contact_email"],
            "[legal_info_url]": item["legal_info_url"],
        }

        self.replace_in_file(self.subdomain_dir + "/.well-known/" + "ai-plugin.json", replace_mapping_ai_plugin)
        replace_mapping_openapi = {
            "[app_url]": self.app_url,
            "[openapi_title]": item["openapi_title"],
            "[openapi_description]": item["openapi_description"],
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