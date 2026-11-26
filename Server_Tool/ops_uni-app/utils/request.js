// utils/request.js -- 统一网络请求封装
// 自动注入网关地址 + Bearer Token, 统一拦截 401 跳转登录页

const request = (options) => {
  const gateway = uni.getStorageSync('ops_gateway') || ''
  const token = uni.getStorageSync('ops_token') || ''

  return new Promise((resolve, reject) => {
    uni.request({
      url: gateway + options.url,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'Content-Type': 'application/json',
        'Authorization': token ? 'Bearer ' + token : '',
        ...(options.header || {})
      },
      success: (res) => {
        // 401: Token 缺失/过期/无效 -> 清理并跳转登录页
        if (res.statusCode === 401) {
          uni.removeStorageSync('ops_token')
          uni.removeStorageSync('ops_username')
          uni.showToast({ title: '登录已过期, 请重新登录', icon: 'none' })
          setTimeout(() => uni.reLaunch({ url: '/pages/login/login' }), 1500)
          reject(res)
          return
        }
        resolve(res)
      },
      fail: (err) => {
        uni.showToast({ title: '网络连接失败, 请检查网关地址', icon: 'none', duration: 2000 })
        reject(err)
      }
    })
  })
}

export default request
