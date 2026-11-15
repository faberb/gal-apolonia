# Gal Apolonia

A lightweight, static recreation of the Gal Apolonia travel and life journal. It restores the original blush-pink and aqua theme, the selected WordPress logo, the original navigation categories, 46 published articles, and the photographs used in those stories.

## Run the site

The archive uses `fetch()` to load its local JSON, so open it through a local web server rather than directly as a `file://` page.

From this folder, run:

```powershell
py -m http.server 8000
```

Then open [http://localhost:8000](http://localhost:8000). Press `Ctrl+C` in the terminal to stop the server.

Search the archive, filter by Life, Travel, Food, or Kit & Gear, open a story, and select an in-story photo to enlarge it. The site has no framework, build step, remote fonts, or third-party assets.

## Project layout

```text
index.html
assets/
  css/site.css
  images/
    gal-apolonia-logo.png
    posts/                 # Optimized photos referenced by the articles
  js/site.js
data/
  posts.json               # Published story copy, categories, tags, and image links
  media-manifest.json      # Source-to-optimized-image map for re-importing the archive
tools/
  import_wordpress.py      # Exports published content from a WordPress SQL dump
  optimize-media.ps1       # Creates the optimized local image files
  test_import_wordpress.py
```

The five posts marked as drafts in the backup are intentionally not included. `data/posts.json` contains the 46 posts that were published. The SQL backups, WordPress configuration, logs, other uploads, and account data are not included in this repository.

## Re-import the archive

Keep the original SQL backup and uploads outside the repository. From this folder, run:

```powershell
py tools\import_wordpress.py --database ..\db5st4wwv3mzny.sql --uploads ..\public_html\wp-content\uploads --output .
powershell -NoProfile -ExecutionPolicy Bypass -File tools\optimize-media.ps1 -UploadsDirectory ..\public_html\wp-content\uploads -MaxDimension 1400 -Quality 76
```

The media step resizes JPEGs and converts oversized animated GIFs to a compact still image to keep the repository practical. Small GIFs remain animated. Python uses only its standard library; image optimization uses Windows' built-in `System.Drawing`.

Run the import-tool tests with:

```powershell
py -m unittest tools\test_import_wordpress.py
```

## GitHub Pages

The source repository stays private. Its current GitHub Pages settings say a private repository needs an upgrade or must be made public before Pages can be enabled; restricting a published Pages site to private access requires GitHub Enterprise. No visibility change or public deployment has been made.
