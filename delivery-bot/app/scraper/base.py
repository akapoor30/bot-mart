class BaseScraper:
    async def search_product(self, product_name: str, pincode: str):
        """Must return a dict with name, price, and store name"""
        raise NotImplementedError