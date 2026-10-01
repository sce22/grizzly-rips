"""Look up your club's EA ID:  python -m fcapp.find_club "My Club Name" [platform]"""
import sys

from .ea_client import EAClient


def main():
    if len(sys.argv) < 2:
        sys.exit('Usage: python -m fcapp.find_club "Club Name" [common-gen5|common-gen4]')
    platform = sys.argv[2] if len(sys.argv) > 2 else "common-gen5"
    results = EAClient(platform).search_clubs(sys.argv[1])
    if not results:
        print("No clubs found. Check spelling, or try platform common-gen4 (PS4/Xbox One).")
    for c in results:
        info = c.get("clubInfo", {})
        print(f"{info.get('name'):30}  club_id={c.get('clubId'):>10}  "
              f"games={c.get('gamesPlayed')}  W-D-L={c.get('wins')}-{c.get('ties')}-{c.get('losses')}")


if __name__ == "__main__":
    main()
