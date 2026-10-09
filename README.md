# Shiori VPM listing

VCC / ALCOM 向けのパッケージ一覧（`index.json`）を GitHub Pages で配信するリポジトリです。
対象は [shiori](https://github.com/yaito3014/shiori) と [shiori-vrchat](https://github.com/yaito3014/shiori-vrchat)。

## 使う側

公開ページの「VCC / ALCOM に追加」ボタンを押すか、`index.json` の URL をリポジトリとして追加してください。

## 仕組み

- 各パッケージのリポジトリで `vX.Y.Z` タグを push すると、そのリポジトリの Release ワークフローが
  `git archive` で zip を作り、`package.json` と SHA-256 と一緒に GitHub Release に添付します。
- このリポジトリの `build.py` が `sources.json` に書かれたリポジトリの Release を読み、
  各 `package.json` に `url`（zip）と `zipSHA256` を足して `index.json` にまとめます。
- `Publish listing` ワークフローが `main` への push、6 時間ごと、手動、
  パッケージ側からの `repository_dispatch`（`package-released`）で走り、GitHub Pages に配信します。

## 初回の設定

1. リポジトリの Settings > Pages で Source を **GitHub Actions** にする
   （`gh api repos/<owner>/<repo>/pages -X POST -f build_type=workflow` でも可）。
2. パッケージ側のリポジトリで、リリース直後に一覧を更新したい場合は
   変数 `VPM_LISTING_REPO`（例: `yaito3014/vpm-listing`）と、
   このリポジトリに contents: read/write を持つ fine-grained PAT を秘密 `VPM_LISTING_TOKEN` として置く。
   置かなくても 6 時間以内に反映されます。

## ローカルで試す

```
GITHUB_TOKEN=$(gh auth token) python3 build.py --url https://yaito3014.github.io/vpm-listing/index.json --out _site
```
