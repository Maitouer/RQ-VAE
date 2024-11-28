import pandas as pd
import torch
from torch_geometric.data import HeteroData
from torch_geometric.datasets import MovieLens1M

from data.preprocessing import MovieLensPreprocessingMixin


class RawMovieLens1M(MovieLens1M, MovieLensPreprocessingMixin):
    MOVIE_HEADERS = ["movieId", "title", "genres"]
    USER_HEADERS = ["userId", "gender", "age", "occupation", "zipCode"]
    RATING_HEADERS = ["userId", "movieId", "rating", "timestamp"]

    def __init__(self, root, transform=None, pre_transform=None, force_reload=False) -> None:
        super(RawMovieLens1M, self).__init__(root, transform, pre_transform, force_reload)

    def _load_ratings(self):
        return pd.read_csv(
            self.raw_paths[2],
            sep="::",
            header=None,
            names=self.RATING_HEADERS,
            encoding="ISO-8859-1",
            engine="python",
        )

    def process(self, max_seq_len=None) -> None:
        data = HeteroData()
        ratings_df = self._load_ratings()

        # Process movie data:
        full_df = pd.read_csv(
            self.raw_paths[0],
            sep="::",
            header=None,
            index_col="movieId",
            names=self.MOVIE_HEADERS,
            encoding="ISO-8859-1",
            engine="python",
        )
        df = self._remove_low_occurrence(ratings_df, full_df, "movieId")
        movie_mapping = {idx: i for i, idx in enumerate(df.index)}

        genres = self._process_genres(df["genres"].str.get_dummies("|").values, one_hot=True)
        genres = torch.from_numpy(genres).to(torch.float)

        data["movie"].x = genres
        # Process user data:
        full_df = pd.read_csv(
            self.raw_paths[1],
            sep="::",
            header=None,
            index_col="userId",
            names=self.USER_HEADERS,
            dtype="str",
            encoding="ISO-8859-1",
            engine="python",
        )
        df = self._remove_low_occurrence(ratings_df, full_df, "userId")
        user_mapping = {idx: i for i, idx in enumerate(df.index)}

        age = df["age"].str.get_dummies().values.argmax(axis=1)[:, None]
        age = torch.from_numpy(age).to(torch.float)

        gender = df["gender"].str.get_dummies().values[:, 0][:, None]
        gender = torch.from_numpy(gender).to(torch.float)

        occupation = df["occupation"].str.get_dummies().values.argmax(axis=1)[:, None]
        occupation = torch.from_numpy(occupation).to(torch.float)

        data["user"].x = torch.cat([age, gender, occupation], dim=-1)

        self.int_user_data = df
        # Process rating data:
        df = self._remove_low_occurrence(ratings_df, ratings_df, ["userId", "movieId"])
        src = [user_mapping[idx] for idx in df["userId"]]
        dst = [movie_mapping[idx] for idx in df["movieId"]]
        edge_index = torch.tensor([src, dst])
        data["user", "rates", "movie"].edge_index = edge_index

        rating = torch.from_numpy(df["rating"].values).to(torch.long)
        data["user", "rates", "movie"].rating = rating

        time = torch.from_numpy(df["timestamp"].values)
        data["user", "rates", "movie"].time = time

        data["movie", "rated_by", "user"].edge_index = edge_index.flip([0])
        data["movie", "rated_by", "user"].rating = rating
        data["movie", "rated_by", "user"].time = time

        df["movieId"] = df["movieId"].apply(lambda x: movie_mapping[x])

        rolling = max_seq_len is not None
        data["user", "rated", "movie"].history = self._generate_user_history(
            df, rolling=rolling, window_size=max_seq_len
        )

        if self.pre_transform is not None:
            data = self.pre_transform(data)

        self.save([data], self.processed_paths[0])
