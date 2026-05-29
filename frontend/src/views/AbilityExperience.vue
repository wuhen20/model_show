<script setup lang="ts">
import { ref } from 'vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { abilityCategories, abilityCards, frameworkLayers } from '@/data/models'

const activeCategory = ref('language')
</script>

<template>
  <div class="app-layout">
    <Header title="人工智能分部 · 模型微调组" subtitle="Model Capability Showcase & Experience Center" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="hero-section">
          <div class="hero-content">
            <h1 class="hero-title">多模态模型能力展示中心</h1>
            <p class="hero-desc">统一展示语言、视觉、时序、语音四大方向模型能力，服务电力业务场景，赋能智能决策与高效运维</p>
          </div>
          <div class="hero-stats">
            <div class="stat-card">
              <div class="stat-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                  <path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/>
                </svg>
              </div>
              <span class="stat-number">30+</span>
              <span class="stat-label">能力接口</span>
            </div>
            <div class="stat-card">
              <div class="stat-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00ff88" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                </svg>
              </div>
              <span class="stat-number">10+</span>
              <span class="stat-label">业务场景</span>
            </div>
            <div class="stat-card">
              <div class="stat-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffaa00" stroke-width="2">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="M12 6v6l4 2"/>
                </svg>
              </div>
              <span class="stat-number">4</span>
              <span class="stat-label">模型方向</span>
            </div>
            <div class="stat-card">
              <div class="stat-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ff5555" stroke-width="2">
                  <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                  <path d="M2 17l10 5 10-5"/>
                  <path d="M2 12l10 5 10-5"/>
                </svg>
              </div>
              <span class="stat-number">1</span>
              <span class="stat-label">统一门户</span>
            </div>
          </div>
        </div>

        <div class="main-section">
          <div class="section-left">
            <div class="category-tabs">
              <button
                v-for="category in abilityCategories"
                :key="category.id"
                class="category-tab"
                :class="{ active: activeCategory === category.id }"
                @click="activeCategory = category.id"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path v-if="category.id === 'language'" d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  <path v-else-if="category.id === 'vision'" d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                  <path v-else-if="category.id === 'timeseries'" d="M18 20V10M12 20V4M6 20v-6"/>
                  <path v-else d="M12 19c-2 0-3.98-1.26-5.38-3H5a2 2 0 0 1 2-2h2.12C8.98 8.26 10 7 12 7s3.02 1.26 4.38 3H19a2 2 0 0 1 2 2h-2.12C15.02 17.74 14 19 12 19z"/>
                </svg>
                <span>{{ category.name }}</span>
                <span class="category-count">{{ category.count }}类</span>
              </button>
            </div>

            <div class="ability-cards">
              <div v-for="card in abilityCards" :key="card.id" class="ability-card">
                <div class="card-icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                    <path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/>
                  </svg>
                </div>
                <div class="card-content">
                  <div class="card-header">
                    <span class="card-title">{{ card.name }}</span>
                    <span class="card-tag">{{ card.tag }}</span>
                  </div>
                  <span class="card-type">{{ card.type }}</span>
                  <p class="card-desc">{{ card.description }}</p>
                </div>
              </div>
            </div>
          </div>

          <div class="section-right">
            <div class="framework-section">
              <h3 class="section-title">统一能力架构</h3>
              <div class="framework-list">
                <div v-for="(layer, index) in frameworkLayers" :key="layer.name" class="framework-item">
                  <div class="layer-index">{{ index + 1 }}</div>
                  <div class="layer-content">
                    <span class="layer-name">{{ layer.name }}</span>
                    <p class="layer-desc">{{ layer.description }}</p>
                  </div>
                  <div v-if="index < frameworkLayers.length - 1" class="layer-arrow">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                      <path d="M5 12h14M12 5l7 7-7 7"/>
                    </svg>
                  </div>
                </div>
              </div>
            </div>

            <div class="quick-link-card">
              <div class="link-header">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" stroke-width="2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                <span class="link-title">前往体验</span>
              </div>
              <p class="link-desc">在工作台首页中选择模型，即可开始智能问答体验</p>
              <router-link to="/" class="link-btn">进入问答工作台</router-link>
            </div>
          </div>
        </div>

        <div class="footer-bar">
          <span class="footer-text">模型能力不是单点展示，而是可复用的业务能力资产</span>
          <div class="footer-actions">
            <router-link to="/" class="footer-btn primary">进入问答工作台</router-link>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 12px 16px;
  min-height: 0;
}

.hero-section {
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(0, 255, 136, 0.05) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 16px;
  padding: 20px 32px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.hero-content {
  text-align: center;
  margin-bottom: 24px;
}

.hero-title {
  font-size: 26px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 10px 0;
}

.hero-desc {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  max-width: 700px;
  margin: 0 auto;
}

.hero-stats {
  display: flex;
  justify-content: center;
  gap: 32px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 18px 28px;
  background: rgba(17, 24, 39, 0.8);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
}

.stat-icon {
  margin-bottom: 10px;
}

.stat-number {
  font-size: 28px;
  font-weight: 700;
  color: #00d4ff;
}

.stat-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 4px;
}

.main-section {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 12px;
  margin-bottom: 10px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.section-left {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  min-height: 0;
}

.section-right {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.category-tabs {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.category-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.category-tab:hover {
  border-color: rgba(0, 212, 255, 0.4);
}

.category-tab.active {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
  border-color: rgba(0, 212, 255, 0.5);
}

.category-count {
  padding: 2px 8px;
  background: rgba(0, 212, 255, 0.2);
  border-radius: 10px;
  font-size: 11px;
}

.ability-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.ability-card {
  display: flex;
  gap: 16px;
  padding: 20px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  transition: all 0.3s ease;
}

.ability-card:hover {
  border-color: rgba(0, 212, 255, 0.4);
  box-shadow: 0 4px 20px rgba(0, 212, 255, 0.1);
}

.card-icon {
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.2) 0%, rgba(0, 255, 136, 0.1) 100%);
  border-radius: 12px;
  flex-shrink: 0;
}

.card-content {
  flex: 1;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.card-tag {
  padding: 2px 8px;
  background: rgba(0, 255, 136, 0.2);
  border-radius: 4px;
  font-size: 11px;
  color: #00ff88;
}

.card-type {
  display: block;
  font-size: 12px;
  color: #00d4ff;
  margin-bottom: 8px;
}

.card-desc {
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.5;
}

.framework-section {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 16px 0;
}

.framework-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.framework-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.layer-index {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 212, 255, 0.2);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #00d4ff;
  flex-shrink: 0;
}

.layer-content {
  flex: 1;
}

.layer-name {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 4px;
}

.layer-desc {
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.5;
}

.layer-arrow {
  display: flex;
  align-items: center;
  color: rgba(0, 212, 255, 0.5);
}

.quick-link-card {
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.08) 0%, rgba(0, 255, 136, 0.05) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
  text-align: center;
}

.link-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 12px;
}

.link-title {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
}

.link-desc {
  margin: 0 0 16px 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.5;
}

.link-btn {
  display: inline-block;
  padding: 10px 24px;
  background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.3s ease;
}

.link-btn:hover {
  box-shadow: 0 0 20px rgba(0, 212, 255, 0.4);
}

.footer-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.95) 0%, rgba(26, 35, 50, 0.9) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  flex-shrink: 0;
}

.footer-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
}

.footer-actions {
  display: flex;
  gap: 12px;
}

.footer-btn.primary {
  padding: 10px 20px;
  background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.3s ease;
}

.footer-btn.primary:hover {
  box-shadow: 0 0 20px rgba(0, 212, 255, 0.4);
}
</style>