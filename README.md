# yaito3014 VPM listing

yaito3014 のパッケージ一覧（VCC / ALCOM 向け `index.json`）を GitHub Pages で配信するリポジトリです。
今は [shiori](https://github.com/yaito3014/shiori) と [shiori-vrchat](https://github.com/yaito3014/shiori-vrchat) が載っています。
新しいパッケージは `sources.json` の `repositories` にリポジトリを足すだけで一覧に入ります（Release ワークフローは同じものを使う）。

## 使う側

- **VCC / ALCOM**: 公開ページの「VCC / ALCOM に追加」ボタンを押すか、`index.json` の URL をリポジトリとして追加。
- **Unity の Package Manager**: `Project Settings > Package Manager` の Scoped Registries に
  URL `https://yaito3014.github.io/vpm-listing`、Scope `com.yaito3014` を追加。

## Unity 用のレジストリ（静的）

`build.py` は VPM 用の `index.json` と一緒に、npm 形式の静的レジストリも出力します。

- `/<パッケージ名>`: packument。署名済み `<name>-<version>.tgz` が添付されたリリースだけが version になる
  （`dist.tarball` は GitHub Release のアセット、`shasum` と `integrity` はビルド時に計算）。
- `/-/all` と `/-/v1/search`: 全パッケージの一覧。静的ホストはクエリ文字列を無視するので、検索は常に全件を返す。
- 確認済み（2026-10-10）: Unity 6000.6 でレジストリから入れると署名は Valid（KakeyamaY）、2022.3.22f1 でも問題なく入る。
- Unity の案内では、スコープ付きレジストリは組織内の配布を想定している。公開して使う点は承知のうえで運用する。

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
