class CRMService:
    async def sync_user(self, user_id: int, user_data: dict):
        """
        Mock CRM Sync logic
        """
        print(f"Syncing user {user_id} with data {user_data} to CRM...")
        return True
        
crm_service = CRMService()
