import asyncio
from app.features.notifications.repository import _send_email

async def main():
    await _send_email("39166287@mynwu.ac.za", "Test Email", "This is a test notification!")
    print("Test email sent.")

asyncio.run(main())
