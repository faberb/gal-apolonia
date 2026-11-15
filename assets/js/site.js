const POSTS_PER_PAGE = 9;
const pageUrl = new URL(window.location.href);
const storyGrid = document.querySelector("#story-grid");
const featuredStories = document.querySelector("#featured-stories");
const searchForm = document.querySelector("#search-form");
const searchInput = document.querySelector("#story-search");
const categoryList = document.querySelector("#category-list");
const archiveCount = document.querySelector("#archive-count");
const archiveEyebrow = document.querySelector("#archive-eyebrow");
const emptyState = document.querySelector("#empty-state");
const filterNote = document.querySelector("#filter-note");
const pagination = document.querySelector("#pagination");
const menuToggle = document.querySelector(".menu-toggle");
const primaryNav = document.querySelector("#primary-nav");
const lightbox = document.querySelector("#lightbox");
let posts = [];
let lastFocusedElement = null;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function formatDate(value) {
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("en", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function postUrl(post) {
  return `?post=${encodeURIComponent(post.slug)}`;
}

function currentFilters() {
  const query = new URLSearchParams(window.location.search);
  return {
    post: query.get("post"),
    category: query.get("category") || "",
    tag: query.get("tag") || "",
    search: query.get("q") || "",
    page: Math.max(1, Number.parseInt(query.get("page") || "1", 10) || 1),
  };
}

function postSearchText(post) {
  return [
    post.title,
    post.excerpt,
    ...post.categories,
    ...post.tags,
    post.content.replace(/<[^>]*>/g, " "),
  ].join(" ").toLocaleLowerCase();
}

function matchesCategory(post, category) {
  if (post.categories.some((name) => name.toLocaleLowerCase() === category.toLocaleLowerCase())) {
    return true;
  }
  if (category.toLocaleLowerCase() === "kit & gear") {
    const subjects = [...post.categories, ...post.tags, post.title, post.excerpt].join(" ");
    return /\b(hiking|hike|skiing|trail|gear|kit)\b/i.test(subjects);
  }
  return false;
}

function filteredPosts(filters) {
  let matches = posts;
  if (filters.category) {
    matches = matches.filter((post) => matchesCategory(post, filters.category));
  }
  if (filters.tag) {
    const tag = filters.tag.toLocaleLowerCase();
    matches = matches.filter((post) => post.tags.some((item) => item.toLocaleLowerCase() === tag));
  }
  if (filters.search) {
    const query = filters.search.trim().toLocaleLowerCase();
    matches = matches.filter((post) => postSearchText(post).includes(query));
  }
  return matches;
}

function categoryLink(label) {
  return `<a class="category-chip" href="?category=${encodeURIComponent(label)}">${escapeHtml(label)}</a>`;
}

function createStoryCard(post) {
  const category = post.categories[0] || "Journal";
  const image = post.image
    ? `<img src="${escapeHtml(post.image)}" alt="${escapeHtml(post.title)}" loading="lazy" decoding="async">`
    : '<span aria-hidden="true">✿</span>';
  const tags = post.tags.slice(0, 3).map((tag) =>
    `<a href="?tag=${encodeURIComponent(tag)}">${escapeHtml(tag)}</a>`
  ).join("");

  return `
    <article class="story-card">
      <a class="story-card-image${post.image ? "" : " story-card-image--empty"}" href="${postUrl(post)}" aria-label="Read ${escapeHtml(post.title)}">
        ${image}
        <span class="story-card-category">${escapeHtml(category)}</span>
      </a>
      <div class="story-card-copy">
        <p class="story-card-meta"><time datetime="${escapeHtml(post.date)}">${escapeHtml(formatDate(post.date))}</time></p>
        <h3><a href="${postUrl(post)}">${escapeHtml(post.title)}</a></h3>
        <p>${escapeHtml(post.excerpt)}</p>
        ${tags ? `<div class="story-card-tags">${tags}</div>` : ""}
      </div>
    </article>
  `;
}

function createFeaturedStories() {
  const featuredSlugs = [
    "hiking-mt-fuji",
    "a-week-in-ho-chi-minh-vietnam",
    "visiting-a-misty-matterhorn",
  ];
  const items = [
    ...featuredSlugs.map((slug) => posts.find((post) => post.slug === slug)).filter(Boolean),
    ...posts.filter((post) => !featuredSlugs.includes(post.slug)),
  ].slice(0, 3);
  if (!items.length) {
    featuredStories.innerHTML = "";
    return;
  }

  featuredStories.innerHTML = items.map((post, index) => {
    const className = index === 0 ? "featured-card-main" : "featured-card-side";
    const image = post.image
      ? `<img src="${escapeHtml(post.image)}" alt="" ${index === 0 ? 'fetchpriority="high"' : 'loading="lazy"'}>`
      : "";
    const category = post.categories[0] || "Journal";
    return `
      <article class="featured-card ${className}">
        ${image}
        <div class="featured-card-copy">
          <span>${escapeHtml(category)} &nbsp;·&nbsp; ${escapeHtml(formatDate(post.date))}</span>
          <h2>${escapeHtml(post.title)}</h2>
        </div>
        <a class="featured-card-link" href="${postUrl(post)}" aria-label="Read ${escapeHtml(post.title)}">${escapeHtml(post.title)}</a>
      </article>
    `;
  }).join("");
}

function updateCategorySelection(filters) {
  if (!categoryList) {
    return;
  }
  const current = filters.category.toLocaleLowerCase();
  for (const link of categoryList.querySelectorAll(".category-chip")) {
    const label = link.textContent.trim().toLocaleLowerCase();
    const selected = current ? current === label : label === "everything";
    link.classList.toggle("is-selected", selected);
    if (selected) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  }
}

function renderPagination(page, pageCount) {
  if (pageCount <= 1) {
    pagination.innerHTML = "";
    return;
  }

  const links = [];
  for (let number = 1; number <= pageCount; number += 1) {
    const params = new URLSearchParams(window.location.search);
    if (number === 1) {
      params.delete("page");
    } else {
      params.set("page", String(number));
    }
    const href = params.toString() ? `?${params}` : "index.html";
    links.push(number === page
      ? `<span class="is-current" aria-current="page">${number}</span>`
      : `<a href="${href}" aria-label="Page ${number}">${number}</a>`);
  }

  if (page < pageCount) {
    const params = new URLSearchParams(window.location.search);
    params.set("page", String(page + 1));
    links.push(`<a class="page-next" href="?${params}">Next <span aria-hidden="true">→</span></a>`);
  }
  pagination.innerHTML = links.join("");
}

function renderArticle(post) {
  const position = posts.findIndex((item) => item.slug === post.slug);
  const newer = posts[position - 1];
  const older = posts[position + 1];
  const tags = [...post.categories, ...post.tags];
  const tagLinks = [...new Set(tags)].map((tag) =>
    `<a href="?tag=${encodeURIComponent(tag)}">${escapeHtml(tag)}</a>`
  ).join("");
  const hero = post.image
    ? `<figure class="article-feature-image"><img src="${escapeHtml(post.image)}" alt="${escapeHtml(post.title)}"></figure>`
    : "";
  const nextLinks = [
    older ? `<a href="${postUrl(older)}">← Older story<br><strong>${escapeHtml(older.title)}</strong></a>` : "",
    newer ? `<a href="${postUrl(newer)}">Newer story →<br><strong>${escapeHtml(newer.title)}</strong></a>` : "",
  ].join("");

  storyGrid.classList.add("is-article");
  storyGrid.innerHTML = `
    <article class="archive-article">
      <a class="article-back" href="index.html#stories"><span aria-hidden="true">←</span> Back to all stories</a>
      <header class="article-header">
        <p class="story-card-meta"><time datetime="${escapeHtml(post.date)}">${escapeHtml(formatDate(post.date))}</time></p>
        <h1>${escapeHtml(post.title)}</h1>
        <p class="article-excerpt">${escapeHtml(post.excerpt)}</p>
      </header>
      ${hero}
      <div class="article-content">${post.content}</div>
      <div class="article-tags" aria-label="Story topics">${tagLinks}</div>
      <nav class="article-next" aria-label="More stories">${nextLinks}</nav>
    </article>
  `;
  pagination.innerHTML = "";
  archiveCount.textContent = "";
  archiveEyebrow.textContent = "From the Gal Apolonia journal";
  document.querySelector("#stories-title").textContent = "A story from the road.";
  document.title = `${post.title} — Gal Apolonia`;
  document.querySelector('meta[name="description"]').content = post.excerpt;
}

function renderArchive(filters) {
  storyGrid.classList.remove("is-article");
  document.querySelector("#stories-title").innerHTML = filters.category
    ? `${escapeHtml(filters.category)} <em>stories.</em>`
    : filters.tag
      ? `Filed under <em>${escapeHtml(filters.tag)}.</em>`
      : filters.search
        ? "Search <em>the journal.</em>"
        : "Notes from <em>here &amp; there.</em>";
  archiveEyebrow.textContent = filters.category
    ? "Stories from this corner of the world"
    : "The story archive";
  document.title = filters.category
    ? `${filters.category} — Gal Apolonia`
    : "Gal Apolonia — Life, travel & everything in between";
  document.querySelector('meta[name="description"]').content =
    "Life, travel, and the little things in between. Read the Gal Apolonia story archive.";

  searchInput.value = filters.search;
  updateCategorySelection(filters);

  const matching = filteredPosts(filters);
  const pageCount = Math.max(1, Math.ceil(matching.length / POSTS_PER_PAGE));
  const page = Math.min(filters.page, pageCount);
  const start = (page - 1) * POSTS_PER_PAGE;
  const visible = matching.slice(start, start + POSTS_PER_PAGE);

  storyGrid.setAttribute("aria-busy", "false");
  storyGrid.innerHTML = visible.map(createStoryCard).join("");
  emptyState.hidden = matching.length > 0;
  archiveCount.textContent = matching.length === 1
    ? "1 story"
    : `${matching.length} stories`;

  const descriptions = [];
  if (filters.search) {
    descriptions.push(`matching “${filters.search}”`);
  }
  if (filters.category) {
    descriptions.push(`in ${filters.category}`);
  }
  if (filters.tag) {
    descriptions.push(`tagged ${filters.tag}`);
  }
  filterNote.hidden = descriptions.length === 0;
  filterNote.textContent = descriptions.length ? `Showing stories ${descriptions.join(" · ")}.` : "";
  renderPagination(page, pageCount);
}

function setPageSectionsVisible(show) {
  for (const id of ["welcome", "about", "kit"]) {
    document.getElementById(id).hidden = !show;
  }
}

function render() {
  const filters = currentFilters();
  const post = posts.find((item) => item.slug === filters.post);
  setPageSectionsVisible(!post);
  if (post) {
    renderArticle(post);
  } else {
    renderArchive(filters);
  }
  closeMenu();
}

function navigate(href) {
  const destination = new URL(href, window.location.href);
  window.history.pushState({}, "", destination);
  render();
  window.requestAnimationFrame(() => {
    document.querySelector("#stories").scrollIntoView({ block: "start" });
  });
}

function closeMenu() {
  if (menuToggle && primaryNav) {
    menuToggle.setAttribute("aria-expanded", "false");
    primaryNav.classList.remove("is-open");
  }
}

function openLightbox(image) {
  const lightboxImage = lightbox.querySelector("img");
  const caption = lightbox.querySelector("p");
  lastFocusedElement = document.activeElement;
  lightboxImage.src = image.src;
  lightboxImage.alt = image.alt;
  caption.textContent = image.closest("figure")?.querySelector("figcaption")?.textContent || image.alt;
  lightbox.hidden = false;
  lightbox.querySelector(".lightbox-close").focus();
}

function closeLightbox() {
  lightbox.hidden = true;
  lightbox.querySelector("img").removeAttribute("src");
  lastFocusedElement?.focus();
}

document.addEventListener("click", (event) => {
  const link = event.target.closest("a");
  if (link?.matches('a[href^="?"]')) {
    event.preventDefault();
    navigate(link.href);
    return;
  }
  if (event.target === lightbox || event.target.closest(".lightbox-close")) {
    closeLightbox();
    return;
  }
  const image = event.target.closest(".article-content figure img");
  if (image) {
    openLightbox(image);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && lightbox && !lightbox.hidden) {
    closeLightbox();
  }
});

window.addEventListener("popstate", render);

if (menuToggle && primaryNav) {
  menuToggle.addEventListener("click", () => {
    const isOpen = menuToggle.getAttribute("aria-expanded") === "true";
    menuToggle.setAttribute("aria-expanded", String(!isOpen));
    primaryNav.classList.toggle("is-open", !isOpen);
  });
}

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const params = new URLSearchParams(window.location.search);
  const query = searchInput.value.trim();
  if (query) {
    params.set("q", query);
  } else {
    params.delete("q");
  }
  params.delete("post");
  params.delete("page");
  const suffix = params.toString() ? `?${params}` : "index.html";
  navigate(suffix);
  searchInput.blur();
});

document.querySelector("#year").textContent = String(new Date().getFullYear());

async function loadArchive() {
  try {
    const response = await fetch("data/posts.json");
    if (!response.ok) {
      throw new Error(`Could not load the story archive (${response.status}).`);
    }
    const archive = await response.json();
    if (!Array.isArray(archive) || archive.length === 0) {
      throw new Error("The story archive is empty or could not be read.");
    }
    posts = archive;
    createFeaturedStories();
    render();
  } catch (error) {
    storyGrid.setAttribute("aria-busy", "false");
    storyGrid.innerHTML = "";
    emptyState.hidden = false;
    emptyState.textContent = error instanceof Error
      ? `${error.message} Start a local server with “py -m http.server 8000” and open http://localhost:8000.`
      : "The story archive could not be loaded.";
    archiveCount.textContent = "Archive unavailable";
  }
}

loadArchive();
