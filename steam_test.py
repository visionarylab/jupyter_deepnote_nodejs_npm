import os
import requests
import pandas as pd

def load_steam_ids(file_path: str = "steamid.txt") -> list:
    """Reads Steam IDs from a text file, ignoring empty lines and comments."""
    if not os.path.exists(file_path):
        print(
            f"Warning: '{file_path}' not found. Returning an empty account list."
        )
        return []

    steam_ids = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            clean_line = line.strip()
            if not clean_line or clean_line.startswith("#"):
                continue
            steam_ids.append(clean_line)
    return steam_ids


def get_owned_games(api_key: str, steam_id: str) -> pd.DataFrame:
    """Fetches owned games with extended appinfo and maps the owner's ID."""
    url = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    params = {
        "key": api_key,
        "steamid": steam_id,
        "include_appinfo": True,
        "include_extended_appinfo": True,  # Pulls advanced metadata flags
        "include_played_free_games": True,
        "format": "json",
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        games_list = data.get("response", {}).get("games", [])

        if not games_list:
            print(f"No games found or profile is private for Steam ID: {steam_id}")
            return pd.DataFrame()

        # Load everything directly into a DataFrame to capture all dynamic columns
        df = pd.DataFrame(games_list)

        # Track ownership mapping
        df["steam_account_id"] = str(steam_id)

        return df

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for Steam ID {steam_id}: {e}")
        return pd.DataFrame()


def merge_steam_accounts(
    api_key: str, steam_ids: list, output_csv: str = "merged_steam_games_extended.csv"
):
    """Fetches games from multiple accounts, dynamically aggregates all available columns

    by appid, and outputs a complete dataset.
    """
    all_account_dfs = []

    for idx, steam_id in enumerate(steam_ids, start=1):
        print(f"Fetching data for Account {idx} ({steam_id})...")
        df = get_owned_games(api_key, steam_id)

        if not df.empty:
            all_account_dfs.append(df)

    if not all_account_dfs:
        print("No data collected from any of the accounts. CSV not created.")
        return

    # Combine all individual dataframes flat
    combined_df = pd.concat(all_account_dfs, ignore_index=True)

    # Automatically identify numerical playtime columns vs descriptive metadata columns
    playtime_cols = [col for col in combined_df.columns if "playtime" in col]
    metadata_cols = [
        col
        for col in combined_df.columns
        if col not in playtime_cols
        and col not in ["appid", "steam_account_id"]
    ]

    # Build an aggregation dictionary dynamically for every column present
    agg_rules = {}

    # 1. Sum up all tracking metrics (forever, 2weeks, deck, windows, mac, linux, etc.)
    for col in playtime_cols:
        agg_rules[col] = "sum"

    # 2. Concat the list of account IDs ownership strings
    agg_rules["steam_account_id"] = lambda x: ", ".join(x.dropna().astype(str).unique())

    # 3. For any other metadata columns from extended info, take the first non-null value
    for col in metadata_cols:
        agg_rules[col] = "first"

    # Group and merge on unique App ID
    merged_df = combined_df.groupby("appid", as_index=False).agg(agg_rules)

    # Optional: Calculate clean hours safely for 'playtime_forever' if it's there
    if "playtime_forever" in merged_df.columns:
        merged_df["playtime_hours"] = (merged_df["playtime_forever"] / 60).round(2)

    # Clean sorting (Fallback to appid if 'name' string column failed to map)
    sort_by = "name" if "name" in merged_df.columns else "appid"
    merged_df = merged_df.sort_values(by=sort_by).reset_index(drop=True)

    # Rename tracking column cleanly
    merged_df = merged_df.rename(columns={"steam_account_id": "steam_account_ids"})

    # Save to file
    merged_df.to_csv(output_csv, index=False)
    print(f"\n Success! Fully detailed data saved to: {output_csv}")
    print(f"Total unique games found: {len(merged_df)}")
    print(f"Columns exported: {list(merged_df.columns)}")


# ==========================================
# CONFIGURATION & EXECUTION
# ==========================================
if __name__ == "__main__":
    STEAM_API_KEY = "E56D21B82A054BEAB30A2C62A538EE1A"

    OUTPUT_FILE = "merged_steam_extended_library.csv"

    # Load account values from local file path
    STEAM_ACCOUNTS = load_steam_ids("steamid.txt")

    print(f"Loaded {len(STEAM_ACCOUNTS)} Steam account(s) from file.")

    if STEAM_ACCOUNTS:
        merge_steam_accounts(
            api_key=STEAM_API_KEY, steam_ids=STEAM_ACCOUNTS, output_csv=OUTPUT_FILE
        )