
class utils():
    
    @staticmethod
    def splitMessage(msg, size = 2000):
        index = 0
        sections = []
        while index + size < len(msg):
            newIndex = msg.rfind('\n', index, index + size + 1)
            if newIndex == -1:
                newIndex = index + size

            sections.append(msg[index:newIndex])
            index = newIndex + 1
        if index < len(msg):
            sections.append(msg[index:])
        return sections

