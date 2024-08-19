from fastcore.utils import *
from fasthtml.basics import *
from fasthtml.starlette import *
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from httpx import AsyncClient
import uvicorn, traceback

#environ= parse_env(Path('discord.ini').read_text())
from os import environ
BOT_TOKEN,PUBLIC_KEY = environ['bot_token'],environ['pubkey']

API_ENDPOINT = 'https://discord.com/api/v10'
headers = {'Authorization': f"Bot {BOT_TOKEN}"}

verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))
cli = AsyncClient()

async def create_dm(user_id):
    return (await cli.post(f"{API_ENDPOINT}/users/@me/channels", json={"recipient_id": user_id}, headers=headers)).json()

async def send_dm(cid, content, components=None):
    json={"content": content, "components": components} if components else {"content": content}
    return (await cli.post(f"{API_ENDPOINT}/channels/{cid}/messages", json=json, headers=headers)).json()

async def delete_message(cid, mid):
    await cli.delete(f"{API_ENDPOINT}/channels/{cid}/messages/{mid}", headers=headers)

async def handle_hook(data):
    dtype = data['type']
    if dtype == 1: return JSONResponse({"type": 1})
    ddata = data['data']
    if dtype == 2 and ddata['type'] == 3:
        user_id = data['member']['user']['id'] if 'member' in data else data['user']['id']
        cid, mid = data['channel_id'], ddata['target_id']
        gid = data['guild_id'] if 'guild_id' in data else '@me'
        mlink = f"https://discord.com/channels/{gid}/{cid}/{mid}"
        mdata = ddata['resolved']['messages'][mid]
        content = f"Message from {mdata['author']['username']}:\n\n{mdata['content']}\n\nLink: {mlink}"
        dm_channel = await create_dm(user_id)
        del_btn = dict(type=2, style=2, emoji={"name": "❌"}, custom_id="delete_dm")
        await send_dm(dm_channel['id'], content, [{"type": 1, "components": [del_btn]}])
        rdata = {"content": f"Message {mlink} sent to your DM", "flags": 64}
        return JSONResponse({"type": 4, "data": rdata})
    if dtype == 3 and ddata['custom_id'] == 'delete_dm':
        await delete_message(data['channel_id'], data['message']['id'])
        return JSONResponse({"type": 4, "data": {"content": "Message deleted", "flags": 64}})
    return JSONResponse({"type": 4, "data": {"content": "Unknown command"}})

app = FastHTML()

@app.get
def index(): return 'App running'

@app.post
async def index(body, X_Signature_Ed25519:str, X_Signature_Timestamp:str, data:dict):
    try: verify_key.verify(f"{X_Signature_Timestamp}{body}".encode(), bytes.fromhex(X_Signature_Ed25519))
    except BadSignatureError: return Response(status_code=401)
    try: return await handle_hook(data)
    except Exception as e:
        print(f"Error processing request: {traceback.format_exc()}")
        return Response(status_code=500)

serve()

