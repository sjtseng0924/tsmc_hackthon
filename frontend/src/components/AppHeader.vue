<script setup>
</script>

<template>
  <header class="app-header">
    <div class="app-title">
      IT 事件助理系統
    </div>
    <nav class="app-nav">
      <RouterLink to="/analysis">分析</RouterLink>
      <RouterLink to="/knowledge-graph">圖譜</RouterLink>
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
