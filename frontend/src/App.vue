<script setup>
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="app-title">
        Incident / Case Knowledge Base
      </div>
      <nav class="app-nav">
        <RouterLink to="/dashboard">Dashboard</RouterLink>
        <RouterLink to="/cases">Cases</RouterLink>
      </nav>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #0f172a;
  color: #f8fafc;
}

.app-title {
  font-size: 18px;
  font-weight: 600;
}

.app-nav a {
  color: #e2e8f0;
  font-weight: 500;
  margin-left: 12px;
}

.app-main {
  width: min(1200px, 92vw);
  margin: 24px auto 64px;
}
</style>
