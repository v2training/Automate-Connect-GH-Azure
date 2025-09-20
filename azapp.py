import asyncio
from azure.identity import DefaultAzureCredential, AzureCliCredential
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.resource import ResourceManagementClient, SubscriptionClient
from msgraph import GraphServiceClient
from msgraph.generated.models.application import Application
from msgraph.generated.models.service_principal import ServicePrincipal
from msgraph.generated.models.federated_identity_credential import FederatedIdentityCredential
from msgraph.generated.applications.applications_request_builder import ApplicationsRequestBuilder


class AzureAppRegManager:
    
    def __init__(self, rgname, cluster, containerreg):
        """Initialize the Azure clients"""
        # Use default credential chain (includes Azure CLI, managed identity, etc.)
        self.credential = DefaultAzureCredential()
        
        # Get subscription ID and tenant ID from Azure SDK
        self.subscription_id, self.tenant_id = self._get_azure_context()
        
        print(f"Connected to Azure:")
        print(f"Tenant ID: {self.tenant_id}")
        print(f"Subscription ID: {self.subscription_id}")
        
        # Initialize clients
        self.graph_client = GraphServiceClient(
            credentials=self.credential,
            scopes=['https://graph.microsoft.com/.default']
        )
        self.auth_client = AuthorizationManagementClient(
            credential=self.credential,
            subscription_id=self.subscription_id
        )
        self.resource_client = ResourceManagementClient(
            credential=self.credential,
            subscription_id=self.subscription_id
        )
                
        # If a resource group name is provided, get its details        
        rgres = self.resource_client.resource_groups.get(rgname)
        
        if not rgres:
            raise Exception(f"Resource group '{rgname}' not found in subscription {self.subscription_id}")

        else:
            self.resource_group = rgname
        
        # assign k8s cluster and container registry
        self.cluster_name = cluster
        self.container_registry = containerreg

        #initialize app registration variables
        self.app_object_id = None

        #app registration created flag
        self.appreg_created = False


    def _get_azure_context(self):
                                
            # Method 1: Try using SubscriptionClient to get default subscription
            try:
                subscription_client = SubscriptionClient(self.credential)
                subscriptions = list(subscription_client.subscriptions.list())
                
                if not subscriptions:
                    raise Exception("No subscriptions found")
                
                # Get the first subscription (or you could implement logic to choose)
                default_subscription = subscriptions[0]
                subscription_id = default_subscription.subscription_id
                tenant_id = default_subscription.tenant_id
                
                print(f"Found subscription: {default_subscription.display_name}")
                return subscription_id, tenant_id
                
            except Exception as e:
                print(f"SubscriptionClient method failed: {str(e)}")
                raise
              

    async def create_app_registration(self, app_name, app_description="App created via Python"):
        try:                        
            # Create the application
            application = Application()
            application.display_name = app_name
            application.description = app_description
            
            request_configuration = ApplicationsRequestBuilder.ApplicationsRequestBuilderGetRequestConfiguration(
                query_parameters=ApplicationsRequestBuilder.ApplicationsRequestBuilderGetQueryParameters(
                    filter=f"displayName eq '{application.display_name}'"
                )
            )

            appexists = await self.graph_client.applications.get(request_configuration)

            # If app registration exists, return existing app details
            if appexists.value and len(appexists.value) > 0:
                print(f"App registration '{app_name}' already exists.")                
                existing_app = appexists.value[0]
                self.app_object_id = existing_app.id
                return {
                    'subscription_id': self.subscription_id,
                    'tenant_id': self.tenant_id,
                    'client_id': existing_app.app_id,
                    'resource_group': self.resource_group,
                    'cluster_name': self.cluster_name,
                    'container_registry': self.container_registry
                }

            # existing app not found, create new one
            else:
                # Create the app registration
                created_app = await self.graph_client.applications.post(application)
                print(f"App registration created successfully!")
                print(f"App Name: {created_app.display_name}")
                print(f"Application ID: {created_app.app_id}")
                print(f"Object ID: {created_app.id}")
                self.appreg_created = True
                self.app_object_id = created_app.id
            
                # Create service principal for the app
                service_principal = ServicePrincipal()
                service_principal.app_id = created_app.app_id
                created_sp = await self.graph_client.service_principals.post(service_principal)
            
                print(f"Service Principal ID: {created_sp.id}")
                print("Waiting for service principal to propagate...")
            
                await asyncio.sleep(30)  # Now properly awaited within async context            
           
                # Assign roles to the service principal (this is sync)
                self.assign_roles_to_app(created_sp.id)

                return {
                    'subscription_id': self.subscription_id,
                    'tenant_id': self.tenant_id,
                    'client_id': created_app.app_id,
                    'resource_group': self.resource_group,
                    'cluster_name': self.cluster_name,
                    'container_registry': self.container_registry
                }

        except Exception as e:
            print(f"Error creating app registration: {str(e)}")
            raise


    def assign_roles_to_app(self, service_principal_id):
        """Assign Azure roles to the service principal"""
        print(f"Assigning roles to service principal...")

        scope=f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}"

        # Define the roles to assign
        roles_to_assign = [
            "b24988ac-6180-42a0-ab88-20f7382dd24c",  # Contributor
            "b1ff04bb-8a4e-4dc4-8eb5-8693973ce19b"   # Azure Kubernetes Service RBAC Cluster Admin
        ]
        
        role_names = [
            "Contributor",
            "Azure Kubernetes Service RBAC Cluster Admin"
        ]       
   

        print(f"assigning roles to Scope: {scope}")

        for role_id, role_name in zip(roles_to_assign, role_names):
            try:
                # Create role assignment
                role_assignment_params = {
                    'role_definition_id': f"/subscriptions/{self.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/{role_id}",
                    'principal_id': service_principal_id,
                    'principal_type': 'ServicePrincipal'
                }
                
                assignment = self.auth_client.role_assignments.create(
                    scope=scope,
                    role_assignment_name=self._generate_guid(),
                    parameters=role_assignment_params
                )
                
                print(f"Assigned role: {role_name}")
                
            except Exception as e:
                print(f"Failed to assign role {role_name}: {str(e)}")
                # Continue with other roles even if one fails
        pass


    async def create_federated_credentials(self, gh_org_user, repo, credential_name=None, branches=None):
        """Create federated credentials for GitHub Actions"""
        
        if self.app_object_id is None:
            raise Exception("App object ID is not set. Create an app registration first.")
            
        if credential_name is None:
            credential_name = f"{gh_org_user}-{repo}-federated"

        if branches is None:
            branches = ["main"]
        

        try:                   
            print(f"Checking if FedCredential name exists: '{credential_name}'")
                        
            existing_credentials = await self.graph_client.applications.by_application_id(
                self.app_object_id).federated_identity_credentials.get()
            
            if not existing_credentials or not existing_credentials.value:
                print(f"No federated credentials exist for this application")
                
            else:
                matching_credentials = [
                    cred for cred in existing_credentials.value 
                    if cred.name == credential_name
                ]

                if matching_credentials:                
                    print(f"Federated credential '{credential_name}' already exists.")
                    return

                else:
                    print(f"Federated credential '{credential_name}' does not exist, creating it...")
            
            # If federated credential does not exist, create it
            print(f"Creating new federated credential '{credential_name}'...")
        
            federated_credential = FederatedIdentityCredential()
            federated_credential.name = credential_name
            federated_credential.issuer = "https://token.actions.githubusercontent.com"
            federated_credential.subject = f"repo:{gh_org_user}/{repo}:ref:refs/heads/{branches[0]}"
            federated_credential.description = f"Federated credential for GitHub repo {repo}"
            federated_credential.audiences = ["api://AzureADTokenExchange"]

            full_repo_path = f"{gh_org_user}/{repo}"
            print(f"Creating federated credential: {credential_name}")
            print(f"GitHub Organization/Username: {gh_org_user}")
            print(f"Repository: {repo}")
            print(f"Subject: repo:{full_repo_path}:ref:refs/heads/{branches[0]}")
            result = await self.graph_client.applications.by_application_id(self.app_object_id).federated_identity_credentials.post(federated_credential)

            print(f"Federated credential created successfully!")
            print(f"Credential ID: {result.id}")            

        except Exception as e:
            print(f"Error creating federated credential: {str(e)}")
            raise


    def _generate_guid(self):
        """Generate a GUID for role assignment"""
        import uuid
        return str(uuid.uuid4())