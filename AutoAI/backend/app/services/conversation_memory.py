class ConversationMemory:
    def __init__(self):
        self.memory = {}

    def get(self, session_id):
        return self.memory.get(session_id, {})

    def update(self, session_id, new_data):
        old = self.memory.get(session_id, {})

        for key, value in new_data.items():
            if value not in [None, "", False]:
                old[key] = value

        self.memory[session_id] = old

        return old

    def clear(self, session_id):
        if session_id in self.memory:
            del self.memory[session_id]


memory = ConversationMemory()