<script setup>
</script>

<template>
  <header class="app-header">
    <div class="app-title">
      Incident / Case Knowledge Base
    </div>
    <nav class="app-nav">
      <RouterLink to="/analysis">Analysis</RouterLink>
    </nav>
  </header>
</template>

<style scoped>
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
</style>
