"""Protect flat user-uploaded documents; generated images retain their own routes."""
from pathlib import PurePosixPath
from starlette.staticfiles import StaticFiles
from starlette.requests import Request
from fastapi import HTTPException
from fastapi.security import HTTPBearer
from lamb.auth_context import get_auth_context
from lamb.uploaded_files import owned_document

class DocumentAwareStaticFiles(StaticFiles):
    async def get_response(self,path,scope):
        parts=PurePosixPath(path).parts
        private=len(parts)==3 and parts[0].casefold()=='public' and parts[1].isdigit()
        if private:
            credentials=await HTTPBearer(auto_error=False)(Request(scope))
            if credentials is None:
                raise HTTPException(401,'Authentication required',headers={'WWW-Authenticate':'Bearer'})
            auth=await get_auth_context(credentials)
            try:
                owned_document('/'.join(parts[1:]),auth.user['id'])
            except ValueError:
                raise HTTPException(404,'Document not found')
        response=await super().get_response(path,scope)
        if private:
            response.headers['Cache-Control']='private, no-store'
            response.headers['Vary']='Authorization'
        return response
