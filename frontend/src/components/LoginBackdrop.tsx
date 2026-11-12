/** 共用的外围知识轨迹。颜色由登录页身份变量提供，装饰不参与交互。 */
export function LoginBackdrop() {
  return (
    <div className="login-backdrop" aria-hidden="true">
      <div className="login-ambient" />
      <svg className="login-traces" viewBox="0 0 1920 1080" preserveAspectRatio="xMidYMid slice" focusable="false">
        <g className="login-contours" fill="none" stroke="currentColor">
          <path d="M-160 350C90 210 163 76 440-50M-110 418C147 246 172 124 454-17" />
          <path d="M1540-70C1580 195 1770 216 1990 390M1584-74C1610 169 1818 202 1986 332" />
          <path d="M-55 840C120 710 130 544 245 445M1510 1054C1630 891 1810 944 1980 724" />
          <path d="M-32 209H100V145H192M1715 790V871H1812V957H1950" />
        </g>
        <g className="login-trace-nodes" fill="var(--backdrop-base)" stroke="currentColor">
          <circle cx="100" cy="209" r="5" /><circle cx="192" cy="145" r="4" />
          <circle cx="1715" cy="790" r="5" /><circle cx="1812" cy="871" r="5" />
          <circle cx="1812" cy="957" r="4" /><circle cx="245" cy="445" r="4" />
        </g>
        <path className="login-landscape-back" d="M-100 1020Q350 779 778 1008T2010 868V1180H-100Z" />
        <path className="login-landscape-front" d="M-100 1070Q430 934 918 1060T2010 968V1180H-100Z" />
      </svg>
    </div>
  )
}
