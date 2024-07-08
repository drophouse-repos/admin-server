from abc import ABC, abstractmethod


class BaseDatabaseOperation(ABC):
    def __init__(self, db):
        self.db = db

    @abstractmethod
    async def create(self, data):
        pass

    @abstractmethod
    async def remove(self, user_id):
        pass

    @abstractmethod
    async def update(self, user_id, data):
        pass

    @abstractmethod
    async def get(self, user_id):
        pass
