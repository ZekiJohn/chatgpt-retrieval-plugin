import os
from subprocess import Popen, PIPE
from datetime import datetime
import random
import string
import re

# def clone_repo():
#     try:
#         subprocess.check_output();
#         clone_repo = subprocess.run(["git", "clone", "https://github.com/openai/chatgpt-retrieval-plugin.git"])
#         return clone_repo.returncode
#     except subprocess.CalledProcessError as e:
#         print("Cathcing error")
#         return "Error: " + e.stderr.decode().strip()


class Deploy:
    def __init__(self, user_id, vdb_index_name, bearer_token, openai_api_key):
        #self.root_dir = os.path.dirname(os.path.abspath(__file__)) # This is your Project Root
        self.user_dir = "./deps/" + datetime.now().strftime("%m-%d-%y") + "__" + str(user_id)
        # self.vdb_index_name = self.slugify(vdb_index_name) + "__" + self.random_string() + "-" + self.random_string()
        self.vdb_index_name = vdb_index_name
        self.openai_api_key = openai_api_key
        self.bearer_token = bearer_token


    def upload_logo(self, logo):
        file_extension = logo.filename.split(".")[-1]
        filename = f"{self.user_dir}/{self.vdb_index_name}/.well-known/logo.{file_extension}"

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
            "[description_for_model]": item["description_for_model"],
            "[description_for_human]": item["description_for_human"],
            "[app_url]": self.vdb_index_name,
            "[contact_email]": item["contact_email"],
            "[legal_info_url]": item["legal_info_url"],
        }
        self.replace_in_file(self.user_dir + "/" + self.vdb_index_name + "/.well-known/" + "ai-plugin.json", replace_mapping_ai_plugin)

        replace_mapping_openapi = {
            "[app_url]": self.vdb_index_name,
            "[openapi_title]": item["openapi_title"],
            "[openapi_description]": item["openapi_description"],
        }
        self.replace_in_file(self.user_dir + "/" + self.vdb_index_name + "/.well-known/" + "openapi.yaml", replace_mapping_openapi)



    def clone_repo(self):
        if not os.path.isdir(self.user_dir):
            # create the directory if it does not exist
            os.makedirs(self.user_dir)

        # git@github.com:openai/chatgpt-retrieval-plugin.git
        p = Popen(["git", "clone", "https://github.com/ZekiJohn/chatgpt-retrieval-plugin.git", self.vdb_index_name], stdout=PIPE, stderr=PIPE, cwd=self.user_dir)
        output, error = p.communicate()
        if p.returncode != 0: 
            print("======> Error Happed", p.returncode, output, str(error))
        else:
            return p.returncode


    def launch(self):
        p = Popen(["flyctl", "launch", "--auto-confirm", "--force-machines", "--no-deploy", "--name", self.vdb_index_name, "--region", "iad"], stdout=PIPE, stderr=PIPE, cwd=self.user_dir + "/" + self.vdb_index_name)
        output, error = p.communicate()
        if p.returncode != 0: 
            print("======> Error Happed", p.returncode, output, str(error))
        else:
            return p.returncode


    # def set_secrets(bearer_token, openai_api_key, pinecone_index):
    def set_secrets(self):
        p = Popen([
            "flyctl", "secrets", "set", 
            "DATASTORE=pinecone",
            "OPENAI_API_KEY=" + self.openai_api_key,
            "BEARER_TOKEN=" + self.bearer_token,
            "PINECONE_API_KEY=9a16c817-69be-4a8d-bdc5-0745880b24dd",
            "PINECONE_ENVIRONMENT=us-central1-gcp",
            "PINECONE_INDEX="+self.vdb_index_name
        ], stdout=PIPE, stderr=PIPE, cwd=self.user_dir + "/" + self.vdb_index_name)
        output, error = p.communicate()
        if p.returncode != 0: 
            print("======> Error Happed", p.returncode, output, str(error))
        else:
            return p.returncode


    def deploy(self):
        p = Popen(["flyctl", "deploy", "--force-machines"], stdout=PIPE, stderr=PIPE, cwd=self.user_dir + "/" + self.vdb_index_name)
        output, error = p.communicate()
        if p.returncode != 0: 
            print("======> Error Happed", p.returncode, output, str(error))
        else:
            return p.returncode

    def replace_in_file(self, file_path, replace_dict):
        """
        Open a file, search for specific strings, replace them with others, and save the updated file.
        """
        # Read the contents of the file
        with open(file_path, "r") as file:
            file_contents = file.read()

        # Replace the search strings with the replace strings
        for search_str, replace_str in replace_dict.items():
            file_contents = file_contents.replace(search_str, replace_str)

        # Write the updated contents back to the file
        with open(file_path, "w") as file:
            file.write(file_contents)
    
    # def random_string(self, length=4):
    #     return ''.join(random.choice(string.ascii_letters) for i in range(length))


    # def slugify(self, s):
    #     s = s.lower().strip()
    #     s = re.sub(r'[^\w\s-]', '', s)
    #     s = re.sub(r'[\s_-]+', '-', s)
    #     s = re.sub(r'^-+|-+$', '', s)
    #     return s
