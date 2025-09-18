# Automate-Connect-GH-Azure
This repo contains a simple python app that will automate initial setup between Azure and GitHub.  
Assumption is this will be used with github actions to connect and deploy to Azure Kubernetes Service.
What is created?
    
    Azure App Registration 
    
    Roles Assigned at Subscription Level
        "AcrPush",
        "Azure Kubernetes Service Cluster User Role", 
        "Azure Kubernetes Service Contributor Role"

    Federated Credential representing the repo.
    Secrets Created in GitHub Repo: used to authenticate to Azure

You have the option to add multiple repositories or one repository. If a repository doesn't exists, the app will close out gracefully and inform you.
A check is performed for existing app registration, federated credential, and repo secrets.  If any exists, they will be skipped.  This means that if I run this twice using the same settings, the code will just run and log output that it skipped creation of each item.


# Prerequisites on Client Machine running this code
- Client is a Windows based operating system (havne't tested on other client OS flavors)
- Install Azure CLI if it's not installed:  https://aka.ms/installazurecliwindows
- VS Code installed: https://code.visualstudio.com/download
- Python installed: https://www.python.org/downloads/windows/  (choose a stable release)


# Initial Setup is to Create GitHub App and PEM Key
This requires a GitHub App created in either GitHub Personal account or the GitHub Organization.  
It's whereever you are hosting your repos that you want to connect with Azure. A github app is used in order for 
the code that runs locally is able to authenticate to github repo's and create secrets if they don't exists.

- Step 1: Create GitHub App

    a. Go to GitHub Settings 
        
        For personal account: https://github.com/settings/apps
        
        For organization: https://github.com/organizations/YOUR_ORG/settings/apps
    

    b. Click "New GitHub App"
    

    c. Fill out the basic information:

        App name: Something like "Secret Manager" or "My Automation App"
        
        Description: Brief description of what it does
        
        Homepage URL: Can be your GitHub profile or any URL
        
        Webhook URL: Leave blank for now (you can use a placeholder like https://example.com)
        
        Webhook secret: Leave blank for now


- Step 2: Configure Permissions

    a. Under Repository permissions, set:
        Actions: Read and Write
        Contents: Read 
        Meatadata: Read

            
- Step 3: Choose where it can be installed and create

    a. Only this account 
    b. Click "Create GitHub App"

- Step 4: Setup a Private Key
        
    a. Click Generate Private Key and it should download a pem file automatically to your downloads folder
    
    Note: Private key will be used by the client to connect to github   


# Setup Windows based client
This is the setup required for running this code locally on a windows based client machine to authenticate to GitHub 
leveraging the previously created github app. This is done using the downloaded pem key and setting up some environment variables.  

- Step 1: Copy the PEM to .SSH directory
    a. copy the PEM from downlaoads directory
    b. paste the PEM file to the following directory
        
        Full Path to copy:
        "c:\users\yourusername\.ssh\"

            
- Step 2: Fetch information that will be used to create environment variable
  
    a. Copy the full private key path including the name of the file
        For Example: "c:\users\v2train\.ssh\mypemfile.pem"
  
    b. Copy the GitHub App install 
         Go to GitHub Settings and scroll down and under Integrations, click Applications
         For the desired github app, click configure button
         The installation id will be the set of digits at the end of the url
        
        For Example: github.com/settings/installations/861022
         Copy off 861022
  
    c. Copy the Github App 
         Go to GitHub Settings and scroll down and click Developer Settings
         Click GitHub Apps and click edit button next to desired github app
         copy the App ID off


# Create Environment Variables 
Create three environment variables representing the information you collected in the previous step.  

- Step 1: Launch PowerShell or Command Prompt
- Step 2: Create Environment Variable representing the private key path, App Install ID, and App 
  
  a. run the following:

        setx GITHUB_APP_PRIVATE_KEY_PATH "C:\Users\yourusername\.ssh\mypemfile.pe
  
        setx GITHUB_APP_INSTALL_ID "your_app_install_id"    
  
        setx GITHUB_APP_ID "your_app_id"

- Step 3: Reboot computer


# Setup Virtual Environment
- Step 1: Launch VS Code and open directory where you cloned this repo
- Step 2: Launch Terminal Session from the file menu: Terminal\New Terminal
- Step 3: Within the terminal session, inspect path and ensure it's the directory that contains this code
- Step 3: Create Virtual Environment: python -m venv .venv
- Step 4: Activate Virtual Environment: .venv/scripts/activate
- Step 5: Install Dependencies:  pip install -r requirements.txt


# Steps to run application
- Step 1: Update main.py and uncomment and add your details

    a. update the following:

        owner = 'username'

        repositories = ['repo1', 'repo2']  # add all repositories that need access

        gh_org_user = 'github user/org that owns the repo'

        app_name = "app-name" #name desired for app registration in Azure

        app_description = "Description of the app registration"

    b. save Changes


- Step 2: Log into Azure
    
    From terminal session run: az login  

- Step 3: Run python application