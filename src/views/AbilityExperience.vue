<script setup lang="ts">
import { ref } from 'vue'
import Header from '@/components/Header.vue'
import Sidebar from '@/components/Sidebar.vue'
import { abilityCategories, abilityCards, frameworkLayers, serviceList } from '@/data/models'

const activeCategory = ref('language')
const inputContent = ref('请输入：分析某台区本月线损异常，结合电量突增、采集失败、倍率档案变化给出疑似原因。')
</script>

<template>
  <div class="app-layout">
    <Header title="人工智能分部 · 模型微调组" subtitle="Model Capability Showcase & Experience Center" />
    <div class="main-content">
      <Sidebar />
      <main class="content-area">
        <div class="hero-section">
          <div class="hero-content">
            <h1 class="hero-title">多模态模型能力展示与体验中心</h1>
            <p class="hero-desc">统一展示、体验与接入语言、视觉、时序、语音四大方向模型能力，服务电力业务场景，赋能智能决策与高效运维。</p>
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
                  <path d="M12 20V10M12 4l8 8-8 8"/>
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
        <div class="experience-section">
          <div class="experience-left">
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
          </div>
          <div class="experience-right">
            <div class="experience-card">
              <div class="card-header">
                <span class="card-title">当前体验能力</span>
              </div>
              <div class="sub-tabs">
                <button class="sub-tab active">业务问答 · 报告生成 · 根因诊断 · 样本构造</button>
                <button class="sub-tab">12类</button>
                <button class="sub-tab">语义任务接口</button>
              </div>
              <div class="input-section">
                <textarea
                  v-model="inputContent"
                  class="input-textarea"
                  placeholder="请输入您的问题或分析需求..."
                  rows="4"
                ></textarea>
                <div class="input-footer">
                  <span class="char-count">{{ inputContent.length }}/1000</span>
                  <div class="input-actions">
                    <button class="action-btn">运行体验</button>
                    <button class="action-btn secondary">上传样例</button>
                  </div>
                </div>
              </div>
            </div>
            <div class="service-catalog">
              <div class="catalog-header">
                <span class="catalog-title">接口服务目录</span>
                <button class="catalog-more">查看全部</button>
              </div>
              <div class="catalog-list">
                <div v-for="service in serviceList" :key="service.id" class="catalog-item">
                  <div class="item-icon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/>
                    </svg>
                  </div>
                  <div class="item-info">
                    <span class="item-name">{{ service.name }}</span>
                    <div class="item-meta">
                      <span class="meta-tag">{{ service.abilityType }}</span>
                      <span class="meta-tag">{{ service.accessMode }}</span>
                    </div>
                  </div>
                  <span class="item-status" :class="service.status === '已接入' ? 'success' : service.status === '测试中' ? 'warning' : service.status === '已封装' ? 'info' : 'danger'">
                    {{ service.status }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="footer-bar">
          <span class="footer-text">模型能力不是单点展示，而是可复用的业务能力资产</span>
          <div class="footer-actions">
            <button class="footer-btn primary">进入能力工作台</button>
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
  min-height: 100vh;
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.hero-section {
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(0, 255, 136, 0.05) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 16px;
  padding: 32px;
  margin-bottom: 20px;
}

.hero-content {
  text-align: center;
  margin-bottom: 32px;
}

.hero-title {
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 12px 0;
}

.hero-desc {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  max-width: 800px;
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
  padding: 20px 32px;
  background: rgba(17, 24, 39, 0.8);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
}

.stat-icon {
  margin-bottom: 12px;
}

.stat-number {
  font-size: 32px;
  font-weight: 700;
  color: #00d4ff;
}

.stat-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 4px;
}

.experience-section {
  display: grid;
  grid-template-columns: 1fr 500px;
  gap: 20px;
  margin-bottom: 20px;
}

.experience-left {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.category-tabs {
  display: flex;
  gap: 12px;
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

.experience-right {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.experience-card {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
}

.card-header {
  margin-bottom: 16px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.sub-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.sub-tab {
  padding: 8px 14px;
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.sub-tab.active {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.input-section {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 10px;
  padding: 16px;
}

.input-textarea {
  width: 100%;
  padding: 12px;
  background: transparent;
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  resize: none;
  outline: none;
  box-sizing: border-box;
}

.input-textarea::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.input-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.char-count {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}

.input-actions {
  display: flex;
  gap: 10px;
}

.action-btn {
  padding: 10px 24px;
  background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-btn:hover {
  box-shadow: 0 0 20px rgba(0, 212, 255, 0.4);
}

.action-btn.secondary {
  background: transparent;
  border: 1px solid rgba(0, 212, 255, 0.3);
  color: #00d4ff;
}

.action-btn.secondary:hover {
  background: rgba(0, 212, 255, 0.1);
}

.service-catalog {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.9) 0%, rgba(26, 35, 50, 0.8) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
  padding: 20px;
}

.catalog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.catalog-title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.catalog-more {
  padding: 4px 10px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  cursor: pointer;
}

.catalog-more:hover {
  background: rgba(0, 212, 255, 0.1);
  color: #00d4ff;
}

.catalog-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.catalog-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(0, 212, 255, 0.05);
  border-radius: 8px;
}

.item-icon {
  color: #00d4ff;
}

.item-info {
  flex: 1;
}

.item-name {
  display: block;
  font-size: 12px;
  color: #fff;
  margin-bottom: 4px;
}

.item-meta {
  display: flex;
  gap: 6px;
}

.meta-tag {
  padding: 2px 6px;
  background: rgba(0, 212, 255, 0.1);
  border-radius: 3px;
  font-size: 10px;
  color: rgba(255, 255, 255, 0.6);
}

.item-status {
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.item-status.success {
  background: rgba(0, 255, 136, 0.2);
  color: #00ff88;
}

.item-status.warning {
  background: rgba(255, 170, 0, 0.2);
  color: #ffaa00;
}

.item-status.info {
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
}

.item-status.danger {
  background: rgba(255, 85, 85, 0.2);
  color: #ff5555;
}

.footer-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.95) 0%, rgba(26, 35, 50, 0.9) 100%);
  border: 1px solid rgba(0, 212, 255, 0.2);
  border-radius: 12px;
}

.footer-text {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
}

.footer-actions {
  display: flex;
  gap: 12px;
}

.footer-btn {
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.footer-btn.primary {
  background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
  border: none;
  color: #fff;
}

.footer-btn.primary:hover {
  box-shadow: 0 0 20px rgba(0, 212, 255, 0.4);
}
</style>
