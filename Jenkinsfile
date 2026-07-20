pipeline {
    agent any
    
    tools {
        // 젠킨스에 설정하신 Maven 이름
        maven 'maven-3.x' 
    }

    stages {
        stage('Checkout') {
            steps {
                // 1. 깃랩에서 소스 코드를 가져옵니다.
                checkout scm
            }
        }
        
        stage('Build') {
            steps {
                // 2. pom.xml이 있는 정확한 경로로 이동하여 빌드합니다.
                dir('apps/backend-api/eyesforu') { 
                    sh 'mvn clean package -DskipTests'
                }
            }
        }
        
        // stage('Test') {
        //     steps {
        //         // 3. 테스트를 실행할 때도 동일한 경로에서 실행해야 합니다.
        //         dir('apps/backend-api/eyesforu') {
        //             sh 'mvn test'
        //         }
        //     }
        // }
        
        stage('Deploy') {
            steps {
                echo '서버 배포 준비 중...'
            }
        }
    }
    
    post {
        success {
            mattermostSend (
                color: 'good', 
                message: "✅ [빌드 성공] 프로젝트: ${env.JOB_NAME} #${env.BUILD_NUMBER}\n변경 사항이 정상적으로 빌드되었습니다."
            )
        }
        failure {
            mattermostSend (
                color: 'danger', 
                message: "🚨 [빌드 실패] 프로젝트: ${env.JOB_NAME} #${env.BUILD_NUMBER}\n파이프라인 로그를 확인해 주세요!"
            )
        }
    }
}