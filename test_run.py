from src.harvester.client import JQuantsClient
client = JQuantsClient()
client.save_daily_bars_to_parquet('2024-05-15')
