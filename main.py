import asyncio
import sys
from azapp import AzureAppRegManager
import githubsec


if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():    
    try:
        # # Fill the following 5 variables with your details below and uncomment them       
        repositories = ['repo1', 'repo2']  # add all repositories that need access
        gh_org_user = 'github user/org that owns the repo'
        app_name = "app-name" #name of app registration in Azure
        app_description = "Description of the app registration"
        rgname = "resource group" #resource group name that host azure resources         
        container_registry = 'acrregistry' #azure container registry name
        aks_enabled = False #set to True if you want to assign AKS role to app registration       
        
        if aks_enabled:
            cluster_name = input("Enter AKS Cluster Name: ")
        
        else:
            cluster_name = None

        # Initialize Azure App Manager
        az_app_manager = AzureAppRegManager(rgname, cluster_name, container_registry, aks_enabled)

        #auth to github
        gh_secret_magic = githubsec.GitHubSecretMagic()

        #ensure all repos exists and accessible
        for repo in repositories:
            print(f'Checking if Repo exists: {repo}')
            repo_check = gh_secret_magic.check_repository_exists(gh_org_user, repo)
            
            if not repo_check['exists'] or not repo_check['accessible']:
                print(f"Repository {gh_org_user}/{repo} does not exist or is not accessible. Exiting.")
                return
            
            else:
                print(f"Repository {gh_org_user}/{repo} exists and accessible. Proceeding...")

        #create app registration and assign roles
        app_info = await az_app_manager.create_app_registration(app_name, app_description)

        for repo in repositories:
            #create federated credentials
            await az_app_manager.create_federated_credentials(gh_org_user, repo)
           
            #get existing secrets
            existing_secrets = gh_secret_magic.get_existing_secrets(gh_org_user, repo)                                    
            
            #create github secrets
            try:                
                for key, value in app_info.items():                    
                    try:
                        #if it's existing secret and app registration not created, skip creating secret
                        if key.upper() in existing_secrets and not az_app_manager.appreg_created:
                            print(f"Secret '{key}' already exists in {repo}, skipping creation.")
                            continue
                        else: 
                            print(f"{key}: {value}")
                            print(f"Creating secret '{key}' in {repo}...")
                            gh_secret_magic.createrepoSecret(gh_org_user, repo, key, value)

                    except Exception as inner_e:
                        print(f"Error creating secret: {inner_e}")

            except Exception as e:
             print(f"Error: {e}")


    except Exception as outer_e:
        print(f"Outer Error: {outer_e} Exiting Program.")


if __name__ == "__main__":
    asyncio.run(main())