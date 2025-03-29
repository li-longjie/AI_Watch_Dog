// 为行为分析按钮添加点击事件
document.addEventListener('DOMContentLoaded', function() {
  const behaviorAnalysisBtn = document.getElementById('behaviorAnalysisBtn');
  
  if (behaviorAnalysisBtn) {
    behaviorAnalysisBtn.addEventListener('click', function() {
      // 跳转到行为分析页面
      window.location.href = '/behavior-analysis.html';
      // 或者使用其他导航方法，例如：
      // loadBehaviorAnalysisComponent();
    });
  }
}); 