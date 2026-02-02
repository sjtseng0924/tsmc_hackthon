<script setup>
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="app-title">
        Incident / Case Knowledge Base
      </div>
      <nav class="app-nav">
        <RouterLink to="/cases">Cases</RouterLink>
      </nav>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
