pipeline {
    agent any
    
    tools {
        // 젠킨스 시스템 설정(Global Tool Configuration)에 등록하신 Maven 이름을 적어주세요.
        // 예: 'maven-3.8', 'Maven' 등
        maven 'maven-3.x' 
    }

    stages {
        stage('Checkout') {
            steps {
                // 1. 깃랩에서 소스 코드를 싹 가져옵니다.
                checkout scm
            }
        }
        
        stage('Build') {
            steps {
                // 2. 소스 코드를 컴파일하고 패키징합니다. (일단 빌드 자체에 집중하기 위해 테스트는 스킵)
                sh 'mvn clean package -DskipTests'
            }
        }
        
        stage('Test') {
            steps {
                // 3. 작성해두신 JUnit 단위 테스트를 실행합니다.
                sh 'mvn test'
            }
        }
        
        stage('Deploy') {
            steps {
                // 4. 추후 Tomcat 서버에 .war/.jar 파일을 배포할 스크립트가 들어갈 자리입니다.
                echo '서버 배포 준비 중...'
            }
        }
    }
    
    // 파이프라인의 모든 작업이 끝난 후 실행되는 알림 영역
    post {
        success {
            // 모든 단계(Build, Test 등)가 무사히 통과했을 때 실행
            mattermostSend (
                color: 'good', 
                message: "✅ [빌드 성공] 프로젝트: ${env.JOB_NAME} #${env.BUILD_NUMBER}\n변경 사항이 서버에 정상적으로 반영되었습니다."
            )
        }
        failure {
            // 어느 한 단계에서라도 에러가 나서 실패했을 때 실행
            mattermostSend (
                color: 'danger', 
                message: "🚨 [빌드 실패] 프로젝트: ${env.JOB_NAME} #${env.BUILD_NUMBER}\n파이프라인 로그를 확인해 주세요!"
            )
        }
    }
}