<template>
  <view class="page">
    <!-- 顶栏 -->
    <view class="header" :style="{ paddingTop: statusBarHeight + 'px' }">
      <text class="back-btn" @click="goBack">< 返回</text>
      <text class="header-title">{{ hostname || ip }}</text>
      <text class="header-ip">{{ ip }}</text>
    </view>

    <!-- 加载 / 空状态 -->
    <view v-if="loading && history.length === 0" class="empty">
      <text class="empty-text">加载中...</text>
    </view>
    <view v-else-if="history.length === 0" class="empty">
      <text class="empty-text" @click="fetchHistory">暂无历史数据, 点击重试</text>
    </view>

    <template v-if="history.length > 0">
      <!-- 趋势图: 纯 CSS 柱状图 -->
      <view class="card">
        <view class="chart-tabs">
          <text :class="['tab', activeTab === 'cpu' ? 'tab-active' : '']"
                @click="activeTab = 'cpu'">CPU</text>
          <text :class="['tab', activeTab === 'mem' ? 'tab-active' : '']"
                @click="activeTab = 'mem'">内存</text>
          <text :class="['tab', activeTab === 'disk' ? 'tab-active' : '']"
                @click="activeTab = 'disk'">磁盘</text>
        </view>

        <!-- Y 轴刻度 + 柱状图 -->
        <view class="chart-wrap">
          <view class="chart-y">
            <text class="y-label">100%</text>
            <text class="y-label">80%</text>
            <text class="y-label">60%</text>
            <text class="y-label">40%</text>
            <text class="y-label">20%</text>
            <text class="y-label">0%</text>
          </view>
          <view class="chart-area">
            <!-- 80% 警戒线 -->
            <view class="warn-line" style="bottom: 80%;"></view>
            <scroll-view scroll-x class="chart-scroll">
              <view class="chart-bars">
                <view class="chart-col" v-for="(h, i) in history" :key="i">
                  <view class="col-bar"
                        :class="{ 'col-warn': h[activeTab] > 80 }"
                        :style="{ height: h[activeTab] + '%' }">
                  </view>
                  <text class="col-val">{{ h[activeTab].toFixed(0) }}</text>
                  <text class="col-time">{{ shortTime(h.time) }}</text>
                </view>
              </view>
            </scroll-view>
          </view>
        </view>
      </view>

      <!-- 当前状态 (取最后一条记录) -->
      <view class="card">
        <text class="card-title">当前状态</text>
        <view class="status-grid">
          <view class="status-item">
            <text class="status-val" :class="{ 'val-warn': latest.cpu > 80 }">
              {{ latest.cpu.toFixed(1) }}%</text>
            <text class="status-name">CPU</text>
          </view>
          <view class="status-item">
            <text class="status-val" :class="{ 'val-warn': latest.mem > 80 }">
              {{ latest.mem.toFixed(1) }}%</text>
            <text class="status-name">内存</text>
          </view>
          <view class="status-item">
            <text class="status-val" :class="{ 'val-warn': latest.disk > 80 }">
              {{ latest.disk.toFixed(1) }}%</text>
            <text class="status-name">磁盘</text>
          </view>
        </view>
      </view>

      <!-- 服务状态 + 重启按钮 -->
      <view class="card">
        <text class="card-title">服务管理</text>
        <view class="svc-item" v-for="svc in svcList" :key="svc.name">
          <view class="svc-info">
            <text class="svc-name">{{ svc.name }}</text>
            <text :class="svc.status === 'active' ? 'tag-ok' : 'tag-err'">
              {{ svc.status }}
            </text>
          </view>
          <text class="btn-restart" :class="{ 'btn-disabled': restarting }"
                @click="confirmRestart(svc.name)">重启</text>
        </view>
        <view v-if="svcList.length === 0" class="empty-svc">
          <text class="empty-text">无服务信息</text>
        </view>
      </view>
    </template>
  </view>
</template>

<script>
import request from '../../utils/request.js'

export default {
  data() {
    return {
      statusBarHeight: 0,
      ip: '',
      hostname: '',
      history: [],
      svcList: [],
      loading: false,
      restarting: false,
      activeTab: 'cpu'
    }
  },
  computed: {
    latest() {
      if (this.history.length === 0) return { cpu: 0, mem: 0, disk: 0 }
      return this.history[this.history.length - 1]
    }
  },
  onLoad(options) {
    this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0
    this.ip = options.ip || ''
    if (this.ip) this.fetchHistory()
  },
  methods: {
    goBack() { uni.navigateBack() },

    shortTime(t) {
      // "11-20 14:30" -> "14:30"
      if (!t) return ''
      const parts = t.split(' ')
      return parts.length > 1 ? parts[1] : t
    },

    // 解析服务状态字符串
    parseSvcPairs(svcStr) {
      if (!svcStr || svcStr === '-') return []
      return svcStr.split(',').map(s => {
        const parts = s.trim().split('=')
        return { name: parts[0] || '', status: parts[1] || 'unknown' }
      }).filter(s => s.name)
    },

    fetchHistory() {
      this.loading = true
      request({ url: '/api/history/' + this.ip }).then(res => {
        if (Array.isArray(res.data) && res.data.length > 0) {
          this.history = res.data.map(h => ({
            ...h,
            cpu:  Number(h.cpu)  || 0,
            mem:  Number(h.mem)  || 0,
            disk: Number(h.disk) || 0
          }))
          this.hostname = res.data[0].hostname || this.ip
          // 解析最后一条记录的服务状态
          const last = res.data[res.data.length - 1]
          this.svcList = this.parseSvcPairs(last.services)
        }
      }).catch(() => {}).finally(() => { this.loading = false })
    },

    confirmRestart(service) {
      if (this.restarting) return
      uni.showModal({
        title: '确认重启',
        content: `确定要重启 ${this.ip} 上的 ${service} 服务吗?`,
        success: (res) => {
          if (res.confirm) this.doRestart(service)
        }
      })
    },

    doRestart(service) {
      this.restarting = true
      uni.showLoading({ title: '正在重启...', mask: true })
      request({
        url: '/api/restart',
        method: 'POST',
        data: { ip: this.ip, service }
      }).then(res => {
        const d = res.data || {}
        uni.showToast({
          title: d.message || (d.success ? '重启成功' : '重启失败'),
          icon: d.success ? 'success' : 'none', duration: 2000
        })
        if (d.success) setTimeout(() => this.fetchHistory(), 3000)
      }).catch(() => {
        uni.showToast({ title: '请求失败', icon: 'none' })
      }).finally(() => {
        uni.hideLoading()
        this.restarting = false
      })
    }
  }
}
</script>

<style>
.page { background: #f0f2f5; min-height: 100vh; padding-bottom: 30rpx; }

/* 顶栏 */
.header { background: #1f2937; padding: 24rpx 30rpx;
          display: flex; align-items: center; gap: 16rpx; }
.back-btn { color: #60a5fa; font-size: 28rpx; }
.header-title { color: #fff; font-size: 32rpx; font-weight: 600; flex: 1; }
.header-ip { color: #64748b; font-size: 24rpx; }

/* 通用卡片 */
.card { background: #fff; margin: 20rpx 24rpx 0; border-radius: 16rpx;
        padding: 28rpx; box-shadow: 0 2rpx 8rpx rgba(0,0,0,.06); }
.card-title { display: block; font-size: 28rpx; font-weight: 600;
              color: #1f2937; margin-bottom: 20rpx; }

/* 趋势图 Tab */
.chart-tabs { display: flex; gap: 16rpx; margin-bottom: 20rpx; }
.tab { padding: 10rpx 28rpx; border-radius: 8rpx; font-size: 24rpx;
       background: #f3f4f6; color: #6b7280; }
.tab-active { background: #3b82f6; color: #fff; }

/* 趋势图区域 */
.chart-wrap { display: flex; height: 320rpx; }
.chart-y { width: 70rpx; display: flex; flex-direction: column;
           justify-content: space-between; padding-right: 8rpx; }
.y-label { font-size: 18rpx; color: #9ca3af; text-align: right; }
.chart-area { flex: 1; position: relative; border-left: 1px solid #e5e7eb;
              border-bottom: 1px solid #e5e7eb; }
.warn-line { position: absolute; left: 0; right: 0; height: 1px;
             background: #fca5a5; border-top: 1px dashed #ef4444; z-index: 1; }
.chart-scroll { width: 100%; height: 100%; }
.chart-bars { display: flex; align-items: flex-end; height: 100%;
              padding: 0 4rpx; min-width: 100%; }
.chart-col { flex: 1; min-width: 40rpx; display: flex; flex-direction: column;
             align-items: center; justify-content: flex-end; height: 100%;
             position: relative; }
.col-bar { width: 60%; border-radius: 4rpx 4rpx 0 0; background: #60a5fa;
           min-height: 4rpx; transition: height .3s; }
.col-warn { background: #ef4444; }
.col-val { font-size: 16rpx; color: #6b7280; margin-top: 2rpx;
           position: absolute; top: -28rpx; }
.col-time { font-size: 14rpx; color: #9ca3af; position: absolute;
            bottom: -32rpx; white-space: nowrap; }

/* 当前状态网格 */
.status-grid { display: flex; justify-content: space-around; }
.status-item { text-align: center; }
.status-val { display: block; font-size: 36rpx; font-weight: 700; color: #1f2937; }
.status-name { font-size: 22rpx; color: #9ca3af; }
.val-warn { color: #ef4444; }

/* 服务管理 */
.svc-item { display: flex; justify-content: space-between; align-items: center;
            padding: 16rpx 0; border-bottom: 1px solid #f3f4f6; }
.svc-info { display: flex; align-items: center; gap: 12rpx; }
.svc-name { font-size: 28rpx; color: #1f2937; }
.tag-ok  { background: #dcfce7; color: #16a34a; padding: 4rpx 14rpx;
           border-radius: 6rpx; font-size: 22rpx; }
.tag-err { background: #fee2e2; color: #dc2626; padding: 4rpx 14rpx;
           border-radius: 6rpx; font-size: 22rpx; }
.btn-restart { background: #fee2e2; color: #dc2626; font-size: 24rpx;
               padding: 10rpx 24rpx; border-radius: 8rpx; }
.btn-disabled { opacity: 0.5; }
.empty-svc { padding: 20rpx 0; }

/* 空状态 */
.empty { display: flex; justify-content: center; align-items: center; height: 400rpx; }
.empty-text { font-size: 28rpx; color: #9ca3af; }
</style>
