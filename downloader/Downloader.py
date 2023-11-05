
class Downloader:
    def __init__(self, collection, logger, temp_dir, cache_dir, user, password) -> None:
        self.collection = collection
        self.logger = logger
        self.temp_dir = temp_dir
        self.cache_dir = cache_dir
        self.user = user
        self.password = password

    

