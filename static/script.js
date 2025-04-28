document.addEventListener("DOMContentLoaded", () => {
  fetch("/api/playlists")
    .then(response => response.json())
    .then(playlists => {
      const container = document.getElementById("playlists");
      if (playlists.length === 0) {
        container.innerText = "No playlists found.";
        return;
      }
      const ul = document.createElement("ul");
      playlists.forEach(pl => {
        const li = document.createElement("li");
        const a = document.createElement("a");
        a.textContent = pl.title;
        a.href = `/playlist.html?playlist_id=${pl.playlist_id}`;
        li.appendChild(a);
        ul.appendChild(li);
      });
      container.appendChild(ul);
    })
    .catch(err => {
      console.error(err);
      document.getElementById("playlists").innerText = "Error loading playlists.";
    });
});