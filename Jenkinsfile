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
        
        stage('Test') {
            steps {
                // 3. 테스트를 실행할 때도 동일한 경로에서 실행해야 합니다.
                dir('apps/backend-api/eyesforu') {
                    sh 'mvn test'
                }
            }
        }
        
        stage('Deploy') {
            steps {
                // pom.xml과 Dockerfile이 있는 폴더로 이동해서 작업합니다.
                dir('apps/backend-api/eyesforu') {
                    // 1. 도커 이미지 빌드 (이름을 'eyesforu-backend'로 지정)
                    sh 'docker build -t eyesforu-backend .'
                    
                    // 2. 혹시 기존에 돌고 있는 똑같은 이름의 컨테이너가 있다면 중지하고 삭제합니다. (처음엔 실패할 수 있으니 || true 추가)
                    sh 'docker stop eyesforu-backend || true'
                    sh 'docker rm eyesforu-backend || true'
                    
                    // 3. 방금 만든 새 이미지를 컨테이너로 실행합니다. (8080 포트 사용)
                    sh 'docker run -d -p 8080:8080 --name eyesforu-backend eyesforu-backend'
                }
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